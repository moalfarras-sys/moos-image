"""The conversation's interface: chats, search, new chat, formatted replies and the composer.

Everything runs on stand-ins: a temporary config directory for the chat files, a fake host for
ChatHistory, and a controller subclass that only adds what the requested controller patch adds
(chatHistory, reload_chat, regenerate) and records `send` instead of asking a model.
"""
import os
import re
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ['MIRA_TEST_MODE'] = '1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
if 'XDG_CONFIG_HOME' not in os.environ or 'mira-' not in os.environ['XDG_CONFIG_HOME']:
    _config = tempfile.TemporaryDirectory(prefix='mira-chat-test-')
    os.environ['XDG_CONFIG_HOME'] = _config.name

from PySide6.QtCore import (QCoreApplication, QEvent, QMetaMethod, QMetaObject, QObject, Property, QPoint,  # noqa: E402
                            QPointF, QRectF, QSettings, Qt, QUrl, Signal, Slot, qInstallMessageHandler)
from PySide6.QtGui import QGuiApplication, QInputMethodEvent, QWheelEvent  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

import chat_ui  # noqa: E402
import i18n  # noqa: E402
import mira_memory  # noqa: E402
from models import DictListModel  # noqa: E402

ROOT = Path(__file__).resolve().parent
MINE = [ROOT / 'qml' / 'Mira' / name for name in ('ConversationPanel.qml', 'MessageDelegate.qml', 'CommandDock.qml')]
APP = QGuiApplication.instance() or QGuiApplication([])


def pump(seconds=0.3, until=None):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return until() if until is not None else True


class private_chats:
    """Point mira_memory at a fresh temporary directory for one test."""

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name) / 'mo-dot'
        self.patches = [patch.object(mira_memory, 'DIR', base),
                        patch.object(mira_memory, 'CONVERSATION', base / 'mira-conversation.jsonl'),
                        patch.object(mira_memory, 'THREADS', base / 'mira-threads.json')]
        for p in self.patches:
            p.start()
        return mira_memory

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()


class FakeHost(QObject):
    """Just the parts of the controller ChatHistory touches."""
    toast = Signal(str, str)
    busyChanged = Signal()
    langChanged = Signal()

    def __init__(self, lang='ar'):
        super().__init__()
        self.lang = lang
        self.s = i18n.table(lang)
        self.busy = False
        self.chat = DictListModel(['role', 'text', 'time', 'status', 'title', 'tool'])
        self.toasts, self.reloads, self.regenerated = [], 0, 0
        self.toast.connect(lambda kind, text: self.toasts.append((kind, text)))

    def reload_chat(self):
        self.reloads += 1

    def regenerate(self):
        self.regenerated += 1


def wait_loaded(h, host=None):
    assert pump(3, lambda: h._seq > 0 and not h.state['loading'])
    pump(0.05)


def history(host):
    """A live (not review) ChatHistory; the caller's test has TEST_MODE patched off."""
    h = chat_ui.ChatHistory(host, host)
    wait_loaded(h)            # its first read (the open chat's name) has come back
    return h


class RenderTest(unittest.TestCase):
    def test_paragraphs_code_and_links_get_their_own_direction(self):
        html = chat_ui.render_markdown('هذا **رد عربي** مع [رابط](https://moos.example) و `code`.\n\n'
                                        'English paragraph with https://example.com/x.\n\n'
                                        '```bash\n# تعليق\nls -la /var\n```\n\n- أول\n- VLC\n\n'
                                        'MoOS هو نظام تشغيل ذكي وحديث.')
        body = html[html.index('<body>'):]
        self.assertRegex(body, r"<p[^>]*dir='rtl'[^>]*>هذا")
        self.assertRegex(body, r"<p(?![^>]*dir='rtl')[^>]*>English paragraph")
        self.assertIn('<table', body)                              # a padded code card
        self.assertIn('\u200e# تعليق', body)                       # stays left-to-right though it opens Arabic
        self.assertIn('JetBrains Mono', body)
        self.assertEqual(len(re.findall(r"<li[^>]*dir='rtl'", body)), 2)   # the list reads as one, right-to-left
        self.assertRegex(body, r"<p[^>]*dir='rtl'[^>]*>MoOS هو")   # mostly Arabic: right-to-left
        self.assertIn('href="https://moos.example"', body)
        self.assertIn('#35d8f4', body.lower())
        self.assertNotIn('<body style', html)

    def test_no_raw_html_no_fetched_images_no_unopenable_links(self):
        html = chat_ui.render_markdown('<b>bold</b> <img src="https://x/y.png"> ![logo](https://moos.example/l.png) '
                                        '![local](file:///etc/passwd) [js](javascript:alert(1)) [file](file:///etc/passwd)\n\n'
                                        '[router](http://192.168.evil.com/login) [x](http://127.0.0.1@evil.example/x) '
                                        'http://127.0.0.1.nip.io ![p](http://192.168.1.5@evil.example/p.png)\n\n'
                                        '[home](http://192.168.1.10:8123/lovelace) [api](http://127.0.0.1:8079/api) [dev](http://localhost:3000)')
        body = html[html.index('<body>'):]
        self.assertNotIn('<b>', body)
        self.assertIn('&lt;b&gt;bold&lt;/b&gt;', body)
        self.assertNotIn('<img', body)
        self.assertIn('href="https://moos.example/l.png"', body)  # an image becomes its address, never fetched
        self.assertNotIn('javascript:', body)                      # the link's words stay, its target goes
        self.assertNotIn('href="file:', body)
        self.assertIn('file:///etc/passwd', body)                  # shown, not linked
        # addresses that only start like home: shown as words, never links
        for bad in ('192.168.evil.com', '127.0.0.1@evil.example', '127.0.0.1.nip.io', '192.168.1.5@evil.example'):
            self.assertNotRegex(body, r'href="[^"]*' + re.escape(bad), bad)
        self.assertIn('router', body)
        for good in ('http://192.168.1.10:8123/lovelace', 'http://127.0.0.1:8079/api', 'http://localhost:3000'):
            self.assertIn(f'href="{good}"', body)

    def test_openable_parses_the_address(self):
        yes = ['https://moos.example', 'https://ar.wikipedia.org/wiki/ميرا', 'http://127.0.0.1:8079/x', 'http://localhost/',
               'http://192.168.0.1', 'http://192.168.255.254:8123/a?b=c#d']
        no = ['http://192.168.evil.com/login', 'http://127.0.0.1@evil.example/x', 'http://127.0.0.1.nip.io',
              'https://user:pw@moos.example', 'http://10.0.0.1', 'http://192.168.1', 'http://0300.0250.1.1',
              'http://example.com', 'HTTPS://moos.example', 'ftp://192.168.1.1', 'javascript:alert(1)', 'file:///etc/passwd',
              'https://moos.example\\@evil', 'https://moos .example', 'https://moos.example/\u202egnp', 'https://', 'https://x:99999',
              'http://[::1]/', '']
        self.assertEqual([u for u in yes if not chat_ui.openable(u)], [])
        self.assertEqual([u for u in no if chat_ui.openable(u)], [])
        self.assertEqual(chat_ui.link_label('https://moos.example/guide/'), 'moos.example/guide')
        self.assertEqual(chat_ui.link_label('http://192.168.1.10:8123/x'), 'http://192.168.1.10:8123/x')
        self.assertEqual(chat_ui.link_label('https://аpple.com/login'), 'xn--pple-43d.com/login')   # a look-alike shows
        self.assertEqual(chat_ui.link_label('http://192.168.evil.com'), '')
        self.assertLessEqual(len(chat_ui.link_label('https://moos.example/' + 'a' * 200)), 64)

    def test_an_arabic_table_reads_right_to_left(self):
        html = chat_ui.render_markdown('```\ncode first\n```\n\n| العمود | **القيمة** |\n|---|---|\n| Version | [44](https://moos.example) |\n\n'
                                        '| Name | Value |\n|---|---|\n| a | b |\n')
        tags = re.findall(r'<table[^>]*>', html)
        self.assertEqual(len(tags), 3)                                     # the code card, then the two tables
        self.assertIn('align="right"', tags[1])
        self.assertNotIn('align="right"', tags[2])
        from PySide6.QtGui import QTextDocument, QTextTable
        doc = QTextDocument()
        doc.setHtml(html)
        tables = [f for f in doc.rootFrame().childFrames() if isinstance(f, QTextTable)]
        cells = lambda t: [[t.cellAt(r, c).firstCursorPosition().block().text() for c in range(t.columns())]
                           for r in range(t.rows())]
        # Qt Quick draws every table left to right: the Arabic one's columns are reversed so its first
        # column («العمود») is on the right; formatting and links move with their words
        self.assertEqual(cells(tables[1]), [['القيمة', 'العمود'], ['44', 'Version']])
        self.assertEqual(cells(tables[2]), [['Name', 'Value'], ['a', 'b']])
        self.assertIn('href="https://moos.example"', html)
        self.assertRegex(html, r'font-weight:700;">القيمة')
        for row in range(2):                                               # every cell on the reading side
            for column in range(2):
                block = tables[1].cellAt(row, column).firstCursorPosition().block()
                self.assertTrue(block.blockFormat().alignment() & Qt.AlignRight, (row, column))

    def test_a_reply_is_cut_at_its_fenced_code(self):
        text = ('قبل\n\n```bash\n# تعليق\nls -la\n```\n\nبعد\n\n1. خطوة\n   ```\n   indented stays\n   ```\n'
                '2. التالية\n\n~~~\nunclosed')
        pieces = chat_ui.split_reply(text)
        self.assertEqual([p[0] for p in pieces], ['text', 'code', 'text', 'code'])
        self.assertEqual(pieces[1][1:], ('# تعليق\nls -la', 'bash'))
        self.assertIn('indented stays', pieces[2][1])          # a fence under a list step stays in its text
        self.assertEqual(pieces[3], ('code', 'unclosed', ''))  # an unclosed fence runs to the end
        self.assertEqual(chat_ui.split_reply('no code here'), (('text', 'no code here', ''),))
        self.assertEqual([p[0] for p in chat_ui.split_reply('`one` and ```not a fence``` here')], ['text'])
        self.assertEqual([p[0] for p in chat_ui.split_reply('````md\n```inner```\n````')], ['code'])
        rendered = chat_ui.reply_pieces(text)
        self.assertEqual(rendered[1]['code'], '# تعليق\nls -la')
        self.assertEqual(rendered[1]['lang'], 'bash')
        self.assertIn('\u200e# تعليق', rendered[1]['html'])     # an Arabic comment stays left to right
        self.assertIn("'IBM Plex Sans Arabic'", rendered[1]['html'])
        self.assertNotIn('<table', rendered[1]['html'])
        self.assertIn("dir='rtl'", rendered[0]['html'])
        self.assertEqual(chat_ui.reply_pieces('')[0]['kind'], 'text')

    def test_arabic_in_code_keeps_an_arabic_face(self):
        html = chat_ui.render_markdown('```bash\n# اعرض النشر الحالي\nbootc status\n```\n\nشغّلي `ls` الآن')
        body = html[html.index('<body>'):]
        self.assertIn("'IBM Plex Sans Arabic'", body)
        self.assertNotIn("font-family:'JetBrains Mono','monospace'", body)

    def test_direction_rule(self):
        self.assertTrue(chat_ui.paragraph_rtl('افتح Visual Studio Code'))
        self.assertTrue(chat_ui.paragraph_rtl('MoOS هو نظام تشغيل ذكي'))
        self.assertFalse(chat_ui.paragraph_rtl('The word ميرا means Mira'))
        self.assertFalse(chat_ui.paragraph_rtl('ls -la'))
        self.assertFalse(chat_ui.paragraph_rtl('12:30 · 45%'))

    def test_regenerable(self):
        self.assertEqual(chat_ui.regenerable([{'role': 'user', 'text': 'q'}, {'role': 'mira', 'text': 'a'}]), 'q')
        self.assertEqual(chat_ui.regenerable([{'role': 'user', 'text': 'q'}, {'role': 'mira'}, {'role': 'mira'}]), 'q')
        self.assertEqual(chat_ui.regenerable([{'role': 'user', 'text': 'q'}, {'role': 'action'}, {'role': 'mira'}]), '')
        self.assertEqual(chat_ui.regenerable([{'role': 'user', 'text': 'q'}]), '')
        self.assertEqual(chat_ui.regenerable([{'role': 'mira', 'text': 'hello'}]), '')
        self.assertEqual(chat_ui.regenerable([]), '')
        self.assertFalse(chat_ui.retry_after_error([{'role': 'user', 'text': 'q'}, {'role': 'mira', 'text': 'a'}]))

    def test_reminders_and_card_answers_are_never_redone(self):
        answered = [{'role': 'user', 'text': 'ما هو bootc؟'}, {'role': 'mira', 'text': 'نظام صور.'}]
        self.assertEqual(chat_ui.regenerable(answered + [{'role': 'mira', 'text': '⏰ استرح', 'tool': 'reminder'}]), '')
        self.assertEqual(chat_ui.regenerable(answered + [{'role': 'mira', 'text': '⏰ استرح'}]), '')   # stored before tools were
        for say in i18n.STRINGS['act_cancelled_say'] + i18n.STRINGS['act_choose']:
            card = [{'role': 'user', 'text': 'لا'}, {'role': 'mira', 'text': say}]
            self.assertEqual(chat_ui.regenerable(card), '', say)            # untagged (older) card answer
        self.assertEqual(chat_ui.regenerable([{'role': 'user', 'text': 'نعم'}, {'role': 'mira', 'text': 'x', 'tool': 'cards'}]), '')

    def test_a_question_that_got_only_an_error_may_be_tried_again(self):
        failed = [{'role': 'user', 'text': 'كم الساعة؟'}, {'role': 'error', 'text': 'تعذّر الاتصال', 'status': 'error'}]
        self.assertEqual(chat_ui.regenerable(failed), 'كم الساعة؟')
        self.assertTrue(chat_ui.retry_after_error(failed))
        mixed = failed[:1] + [{'role': 'mira', 'text': 'الساعة'}, failed[1]]
        self.assertEqual(chat_ui.regenerable(mixed), '')
        self.assertFalse(chat_ui.retry_after_error(mixed))
        self.assertEqual(chat_ui.regenerable([{'role': 'mira', 'text': 'a'}, failed[1]]), '')   # no question before it

    def test_dates_read_naturally(self):
        today = datetime(2026, 9, 29).date()
        self.assertEqual(chat_ui.day_label('2026-09-29', 'ar', today), 'اليوم')
        self.assertEqual(chat_ui.day_label('2026-09-28', 'en', today), 'Yesterday')
        self.assertEqual(chat_ui.day_label('2026-09-21', 'ar', today), 'الاثنين 21 أيلول')
        self.assertEqual(chat_ui.day_label('2025-12-31', 'en', today), 'Wednesday 31 December 2025')
        self.assertEqual(chat_ui.day_label('garbage', 'en', today), '')
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc).astimezone()
        self.assertRegex(chat_ui.when_label(now.isoformat(), 'en', now), r'^\d\d:\d\d$')
        self.assertEqual(chat_ui.when_label((now - timedelta(days=1)).isoformat(), 'ar', now), 'أمس')
        self.assertEqual(chat_ui.when_label((now - timedelta(days=40)).isoformat(), 'en', now).split()[-1], 'August')
        self.assertEqual(chat_ui.group_key({'pinned': True, 'updated': now.isoformat()}, now), 'ch_pinned')
        self.assertEqual(chat_ui.group_key({'updated': (now - timedelta(days=3)).isoformat()}, now), 'ch_week')
        self.assertEqual(chat_ui.group_key({'updated': ''}, now), 'ch_older')
        self.assertEqual(chat_ui.STRINGS['ch_week'][0], 'آخر 7 أيام')             # Western digits, as everywhere in Mira

    def test_every_word_exists_in_both_languages(self):
        for key, pair in chat_ui.STRINGS.items():
            self.assertEqual(len(pair), 2, key)
            self.assertTrue(all(isinstance(x, str) and x.strip() for x in pair), key)
            self.assertTrue(key.startswith('ch_'), key)         # never overrides another module's words
        used = set()
        for path in MINE:
            used |= set(re.findall(r'\bmira\.s\.(\w+)', path.read_text()))
        words = i18n.table('en')
        self.assertEqual(sorted(k for k in used if k not in words), [])
        text = ' '.join(a + b for a, b in chat_ui.STRINGS.values())
        self.assertNotRegex(text, r'(?i)fedora|red hat')


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.live = patch.object(chat_ui, 'TEST_MODE', False)
        self.live.start()

    def tearDown(self):
        pump(0.05)
        self.live.stop()

    def test_lists_groups_and_names_the_open_chat(self):
        with private_chats() as m:
            m.add_message('user', 'كم ضوء مضاء؟')
            m.add_message('mira', 'ضوءان.')
            first = m.current_thread()
            m.new_thread()
            m.add_message('user', 'ثبّتي VLC')
            m.pin_thread(first, True)
            host = FakeHost()
            h = history(host)
            wait_loaded(h, host)
            rows = h.threads.rows()
            self.assertEqual([r['title'] for r in rows], ['كم ضوء مضاء؟', 'ثبّتي VLC'])
            self.assertEqual([r['header'] for r in rows], ['المثبّتة', 'اليوم'])
            self.assertEqual(rows[0]['preview'], 'ضوءان.')
            self.assertTrue(rows[1]['current'])
            self.assertEqual(h.state['currentTitle'], 'ثبّتي VLC')
            self.assertEqual(h.state['count'], 2)
            self.assertEqual(h.state['threads'], rows)

    def test_new_open_and_archive_reload_the_visible_chat(self):
        with private_chats() as m:
            m.add_message('user', 'سؤال')
            first = m.current_thread()
            host = FakeHost('en')
            h = history(host)
            wait_loaded(h, host)
            h.newChat()
            self.assertNotEqual(m.current_thread(), first)
            self.assertEqual(host.reloads, 1)
            self.assertEqual(host.toasts[-1], ('info', 'Started a new chat'))
            self.assertEqual(m.recent_messages(), [])
            wait_loaded(h, host)
            h.openThread(first)
            self.assertEqual(m.current_thread(), first)
            self.assertEqual(host.reloads, 2)
            wait_loaded(h, host)
            h.openThread('does-not-exist')
            self.assertEqual(host.toasts[-1], ('error', 'This chat no longer exists'))
            self.assertEqual(host.reloads, 2)
            # archiving the open chat starts a fresh one in its place
            h.archiveThread(first, True)
            self.assertNotEqual(m.current_thread(), first)
            self.assertEqual(host.reloads, 3)
            self.assertIn(('ok', 'Chat archived'), host.toasts)
            wait_loaded(h, host)
            h.showArchived(True)
            wait_loaded(h, host)
            self.assertEqual([r['tid'] for r in h.threads.rows()], [first])
            self.assertEqual(h.threads.rows()[0]['header'], 'Archived')
            self.assertEqual(h.state['current'], m.current_thread())   # the open chat is still known

    def test_nothing_switches_while_mira_is_mid_turn(self):
        with private_chats() as m:
            m.add_message('user', 'سؤال')
            first = m.current_thread()
            host = FakeHost('en')
            h = history(host)
            host.busy = True
            h.newChat()
            h.archiveThread(first, True)
            self.assertEqual(m.current_thread(), first)
            self.assertEqual(host.reloads, 0)
            self.assertEqual(host.toasts[-1], ('pending', 'Wait until Mira finishes her reply'))
            self.assertFalse(m.list_threads()[0]['archived'])

    def test_day_labels_follow_the_language_asked_for(self):
        host = FakeHost('ar')
        h = history(host)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        self.assertEqual(h.dayLabel(yesterday, 'en'), 'Yesterday')
        self.assertEqual(h.dayLabel(yesterday, 'ar'), 'أمس')
        self.assertEqual(h.dayLabel(yesterday, ''), 'أمس')                   # the window's language by default
        self.assertTrue(h.openable('https://moos.example'))
        self.assertFalse(h.openable('http://192.168.evil.com'))
        self.assertEqual(h.linkLabel('https://moos.example/guide'), 'moos.example/guide')

    def test_rename_pin_and_errors_are_reported(self):
        with private_chats() as m:
            m.add_message('user', 'سؤال')
            tid = m.current_thread()
            host = FakeHost('en')
            h = history(host)
            h.renameThread(tid, 'Project plan')
            h.pinThread(tid, True)
            wait_loaded(h, host)
            self.assertEqual(h.threads.rows()[0]['title'], 'Project plan')
            self.assertTrue(h.threads.rows()[0]['pinned'])
            h.renameThread(tid, 'x' * 81)
            self.assertEqual(host.toasts[-1], ('error', 'A chat name is up to 80 characters'))
            h.pinThread('ghost', True)
            self.assertEqual(host.toasts[-1], ('error', 'This chat no longer exists'))
            with patch.object(mira_memory, 'rename_thread', side_effect=ValueError('غير موجودة في النص')):
                h.renameThread(tid, 'x')                  # a name error whose words happen to say «missing»
            self.assertEqual(host.toasts[-1], ('error', 'A chat name is up to 80 characters'))
            with patch.object(mira_memory, 'pin_thread', side_effect=OSError('disk full')):
                h.pinThread(tid, False)
            self.assertEqual(host.toasts[-1], ('error', 'Could not save the change to the chat'))

    def test_search_shows_matches_and_drops_stale_reads(self):
        with private_chats() as m:
            m.add_message('user', 'أين إعدادات الصوت؟')
            m.new_thread()
            m.add_message('user', 'Install VLC')
            host = FakeHost('en')
            h = history(host)
            wait_loaded(h, host)
            h.search('اعدادات')
            wait_loaded(h, host)
            rows = h.threads.rows()
            self.assertEqual(len(rows), 1)
            self.assertIn('إعدادات', rows[0]['preview'])
            self.assertEqual(rows[0]['header'], 'Search results')
            self.assertTrue(h.state['currentTitle'])            # the open chat's name survives a search
            h.on_threads('threads:0', [])                        # an older read arriving late changes nothing
            self.assertEqual(len(h.threads.rows()), 1)
            h.on_threads(f'threads:{h._seq}', {'status': 'error', 'error': 'OSError'})
            self.assertEqual(h.state['error'], 'Could not read the chat history')
            h.search('')
            wait_loaded(h, host)
            self.assertEqual(len(h.threads.rows()), 2)

    def test_regenerate_is_offered_only_for_a_plain_last_reply(self):
        host = FakeHost('en')
        h = history(host)
        self.assertFalse(h.state['canRegenerate'])
        host.chat.append({'role': 'user', 'text': 'q'})
        host.chat.append({'role': 'mira', 'text': 'a'})
        self.assertTrue(h.state['canRegenerate'])
        h.regenerate()
        self.assertEqual(host.regenerated, 1)
        host.busy = True
        host.busyChanged.emit()
        self.assertFalse(h.state['canRegenerate'])
        h.regenerate()
        self.assertEqual(host.regenerated, 1)
        host.busy = False
        host.chat.append({'role': 'user', 'text': 'turn off'})
        host.chat.append({'role': 'action', 'text': 'done', 'status': 'ok'})
        host.chat.append({'role': 'mira', 'text': 'ok'})
        self.assertFalse(h.state['canRegenerate'])
        h.regenerate()
        self.assertEqual(host.regenerated, 1)
        # a reminder that fires after a plain answer takes the offer away
        host.chat.append({'role': 'user', 'text': 'q2'})
        host.chat.append({'role': 'mira', 'text': 'a2'})
        self.assertTrue(h.state['canRegenerate'])
        host.chat.append({'role': 'mira', 'text': '⏰ استرح', 'tool': 'reminder'})
        self.assertFalse(h.state['canRegenerate'])
        # a question that got only an error: «Try again»
        host.chat.append({'role': 'user', 'text': 'q3'})
        host.chat.append({'role': 'error', 'text': 'offline', 'status': 'error'})
        self.assertTrue(h.state['canRegenerate'])
        self.assertTrue(h.state['retry'])
        h.regenerate()
        self.assertEqual(host.regenerated, 2)
        host.chat.append({'role': 'user', 'text': 'q4'})
        self.assertFalse(h.state['canRegenerate'])
        self.assertFalse(h.state['retry'])

    def test_review_data_is_sample_and_touches_nothing(self):
        host = FakeHost('ar')
        self.live.stop()
        try:
            with patch.object(mira_memory, 'list_threads', side_effect=AssertionError('read in review')), \
                    patch.object(chat_ui, 'TEST_MODE', True):
                h = chat_ui.ChatHistory(host, host)
                h.refresh()
                pump(0.1)
        finally:
            self.live.start()
        self.assertEqual(h.state['count'], 5)
        self.assertEqual(h.threads.rows()[0]['header'], 'المثبّتة')


class QmlContractTest(unittest.TestCase):
    """The static half of test_qml's gate for the controls that reach ChatHistory by name."""

    def test_every_history_call_is_a_slot_and_every_lookup_is_declared(self):
        meta = chat_ui.ChatHistory.staticMetaObject
        slots = {bytes(meta.method(i).name().data()).decode() for i in range(meta.methodCount())
                 if meta.method(i).methodType() in (QMetaMethod.Slot, QMetaMethod.Method)}
        props = {meta.property(i).name() for i in range(meta.propertyCount())}
        called, read, lookups = set(), set(), set()
        for path in MINE:
            text = path.read_text()
            called |= set(re.findall(r'\bhistory\.(\w+)\s*\(', text))
            read |= set(re.findall(r'\bhistory\.(\w+)\b(?!\s*\()', text))
            lookups |= set(re.findall(r'\bmira\["(\w+)"\]', text))
        self.assertTrue(called)
        self.assertEqual(sorted(called - slots), [], 'buttons call ChatHistory slots that do not exist')
        self.assertEqual(sorted(read - props - slots), [], 'bindings read ChatHistory properties that do not exist')
        self.assertEqual(sorted(lookups - set(chat_ui.CONTROLLER_HOOKS)), [])
        from controller import Controller
        cmeta = Controller.staticMetaObject
        cprops = {cmeta.property(i).name() for i in range(cmeta.propertyCount())}
        for name in chat_ui.CONTROLLER_HOOKS:        # once the controller exposes it, it must be a property
            if hasattr(Controller, name):
                self.assertIn(name, cprops)

    def test_day_labels_are_asked_in_the_window_language(self):
        calls = re.findall(r'dayLabel\(([^)]*)\)', (ROOT / 'qml' / 'Mira' / 'MessageDelegate.qml').read_text())
        self.assertTrue(calls)
        self.assertTrue(all('mira.lang' in call for call in calls), calls)   # the label follows a switch

    def test_the_lookup_gate_bites(self):
        text = 'onClicked: panel.history.launchMissiles()'
        self.assertEqual(re.findall(r'\bhistory\.(\w+)\s*\(', text), ['launchMissiles'])
        self.assertFalse(hasattr(chat_ui.ChatHistory, 'launchMissiles'))


class ControllerPatchTest(unittest.TestCase):
    """The controller's chat glue (chatHistory, reload_chat, regenerate): always required."""

    def test_the_controller_carries_the_chat_glue(self):
        from controller import Controller
        for name in ('reload_chat', 'regenerate', 'chatHistory'):
            self.assertTrue(hasattr(Controller, name), name)

    def controller(self):
        from controller import Controller
        from review_fakes import FakeBridge
        return Controller(bridge_class=FakeBridge)

    def test_chats_reload_with_verified_results_and_days(self):
        with private_chats() as m:
            c = self.controller()
            c.chat.clear()
            c._add('user', 'شغّلي الضوء')
            c._add('action', 'تأكدت: الضوء يعمل', status='ok', title='home', tool='home_control')
            first = m.current_thread()
            self.assertEqual(c.chatHistory.metaObject().className(), 'ChatHistory')
            c.chatHistory.newChat()
            self.assertEqual(c.chat.count, 0)
            c._add('user', 'سؤال جديد')
            c.chatHistory.openThread(first)
            rows = c.chat.rows()
            self.assertEqual([(r['role'], r['status']) for r in rows], [('user', ''), ('action', 'ok')])
            self.assertRegex(rows[0]['day'], r'^\d{4}-\d\d-\d\d$')

    def test_regenerate_asks_the_same_question_once(self):
        with private_chats() as m:
            c = self.controller()
            c.chat.clear()
            c._add('user', 'اشرحي bootc')
            c._add('mira', 'جواب أول')
            asked = []
            with patch.object(c, '_run_brain', side_effect=asked.append):
                c.regenerate()
            self.assertEqual(asked, ['اشرحي bootc'])
            self.assertEqual([r['role'] for r in c.chat.rows()], ['user'])
            self.assertEqual([r['role'] for r in m.recent_messages()], ['user'])
            c._text_phase = None
            c._add('action', 'تم', status='ok')
            c._add('mira', 'تم.')
            with patch.object(c, '_run_brain', side_effect=asked.append):
                c.regenerate()                      # a turn that acted is never run twice
            self.assertEqual(asked, ['اشرحي bootc'])

    def test_reminders_and_card_answers_are_never_asked_again(self):
        with private_chats() as m:
            c = self.controller()
            c.chat.clear()
            c._add('user', 'ما هو bootc؟')
            c._add('mira', 'نظام صور.')
            c._add('mira', '⏰ استرح', tool='reminder')
            self.assertFalse(c.chatHistory.state['canRegenerate'])
            asked = []
            with patch.object(c, '_run_brain', side_effect=asked.append):
                c.regenerate()
            self.assertEqual(asked, [])
            self.assertEqual([r['text'] for r in m.messages()], ['ما هو bootc؟', 'نظام صور.', '⏰ استرح'])
            # «لا» to a waiting card: the window answers, and tags its own words
            card = {'id': 'a1', 'created': 0}
            with patch.object(c.pending, 'latest', return_value=card), \
                    patch.object(c.pending, 'respond', return_value={'verdict': 'no', 'items': []}):
                self.assertTrue(c._answer_pending('لا', spoken=False))
            self.assertEqual(c.chat.rows()[-1]['tool'], 'cards')
            self.assertEqual(m.messages()[-1]['tool'], 'cards')
            c._add('user', 'نعم')
            with patch.object(c.pending, 'latest', return_value=card), \
                    patch.object(c.pending, 'respond', return_value={'verdict': 'ambiguous'}):
                c._answer_pending('نعم', spoken=False)
            self.assertEqual(c.chat.rows()[-1]['tool'], 'cards')
            self.assertFalse(c.chatHistory.state['canRegenerate'])
            with patch.object(c, '_run_brain', side_effect=asked.append):
                c.regenerate()
            self.assertEqual(asked, [])

    def test_a_question_that_got_only_an_error_is_tried_again(self):
        with private_chats() as m:
            c = self.controller()
            c.chat.clear()
            c._add('user', 'كم الساعة؟')
            c._add('error', 'تعذّر الاتصال', status='error')
            self.assertTrue(c.chatHistory.state['retry'])
            asked = []
            with patch.object(c, '_run_brain', side_effect=asked.append):
                c.chatHistory.regenerate()
            self.assertEqual(asked, ['كم الساعة؟'])
            self.assertEqual([r['role'] for r in c.chat.rows()], ['user', 'error'])    # the error happened; it stays
            self.assertEqual([r['role'] for r in m.recent_messages()], ['user'])        # the model gets the question once

    def test_a_job_result_lands_in_the_chat_it_was_approved_in(self):
        with private_chats() as m:
            c = self.controller()
            c.chat.clear()
            c._add('user', 'نظّفي الذاكرة المؤقتة')
            first = m.current_thread()
            item = {'id': 'job1', 'kind': 'moai', 'title_ar': 'تنظيف', 'title_en': 'Clean up', 'detail': '',
                    'payload': {'name': 'clean_caches', 'args': {}, 'category': 'confirm'}}
            with patch.object(c.worker, 'run'):
                c._start_action(item)
            c.chatHistory.newChat()                                  # the owner moves on while the job runs
            self.assertNotEqual(m.current_thread(), first)
            c._on_action_done('job1', {'status': 'ok', 'name': 'clean_caches'})
            self.assertEqual([r['role'] for r in c.chat.rows()], [])            # not in the chat now open
            self.assertEqual([(r['role'], r['status']) for r in m.messages(first)],
                             [('user', ''), ('action', 'pending'), ('action', 'ok')])
            self.assertEqual(m.messages(), [])

    def test_opening_a_chat_drops_the_live_voice_context(self):
        # The voice session lives on the voice thread: the Qt thread asks LiveVoice.forget_context()
        # (thread-safe) and never sets the link's fields itself.
        from types import SimpleNamespace
        with private_chats():
            c = self.controller()
            forgot = []
            c.bridge.voice = SimpleNamespace(forget_context=lambda: forgot.append('echo'))
            c.desk = SimpleNamespace(voice=SimpleNamespace(forget_context=lambda: forgot.append('desk')),
                                     shutdown=lambda: None)
            c.chatHistory.newChat()
            self.assertEqual(sorted(forgot), ['desk', 'echo'])

    def test_the_real_live_voice_holds_the_request_until_its_loop_applies_it(self):
        from types import SimpleNamespace
        from live_voice import LiveVoice
        with private_chats():
            c = self.controller()
            voice = LiveVoice(SimpleNamespace(is_connected=False), {}, lambda *a: None)   # built off any loop
            link = SimpleNamespace(dirty=False, idle_closed=False)
            voice.link = link
            c.bridge.voice = voice
            c.chatHistory.newChat()
            self.assertTrue(voice._forget_pending)
            self.assertFalse(link.dirty or link.idle_closed, 'the Qt thread touched the voice link itself')

    def test_the_window_opens_only_parsed_addresses(self):
        import controller as module
        c = self.controller()
        with patch.object(module.QDesktopServices, 'openUrl') as opened:
            for url in ('http://192.168.evil.com/login', 'http://127.0.0.1@evil.example/x', 'http://127.0.0.1.nip.io',
                        'javascript:alert(1)'):
                c.openUrl(url)
            self.assertEqual(opened.call_count, 0)
            c.openUrl('https://moos.example')
            c.openUrl('http://192.168.1.10:8123')
            self.assertEqual(opened.call_count, 2)


# ── the real window, with a controller that has the requested patch's API ─────
_window = {}


def window():
    if _window:
        return _window['w'], _window['c'], _window['messages']
    from controller import Controller
    from faces import FaceProvider
    from review_fakes import FakeBridge
    QSettings.setDefaultFormat(QSettings.IniFormat)

    class RecordingHistory(chat_ui.ChatHistory):
        """The review-mode history; opening a chat is recorded (the review chats exist nowhere)."""
        def __init__(self, host, parent=None):
            super().__init__(host, parent)
            self.opened = []

        @Slot(str)
        def openThread(self, tid):
            self.opened.append(tid)

    class PatchedController(Controller):
        """Controller + only what the requested patch adds; `send` and `copyText` are recorded."""
        def __init__(self):
            super().__init__(bridge_class=FakeBridge)
            self._chat_history = getattr(self, '_chat_history', None) or RecordingHistory(self, self)
            if not isinstance(self._chat_history, RecordingHistory):
                self._chat_history = RecordingHistory(self, self)
            self.sent, self.copied = [], []

        chatHistory = Property(QObject, lambda self: self._chat_history, constant=True)

        @Slot(str)
        def copyText(self, text):
            self.copied.append(text)

        def reload_chat(self):
            self.chat.clear()

        @Slot()
        def regenerate(self):
            pass

        @Slot(str)
        def send(self, text):
            self.sent.append(text)

    messages = []

    def handler(mode, context, message):
        if not any(word in message for word in ('ShaderEffect', 'shader', 'QRhi', 'rhi', 'qsb')):
            messages.append(message)
    qInstallMessageHandler(handler)
    controller = PatchedController()
    engine = QQmlApplicationEngine()
    engine.addImageProvider('mira', FaceProvider())
    engine.addImportPath(str(ROOT / 'qml'))
    engine.rootContext().setContextProperty('mira', controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
    root = engine.rootObjects()[0]
    root.setWidth(1480)
    root.setHeight(920)
    controller.start()
    pump(0.6)
    _window.update(w=root, c=controller, messages=messages, engine=engine)
    return root, controller, messages


def visible(root, name):
    return next(o for o in root.findChildren(QObject, name) if o.property('visible'))


def scene_rect(item):
    at = item.mapToScene(QPointF(0, 0))
    return QRectF(at.x(), at.y(), item.property('width'), item.property('height'))


def inside(item, name):
    """Is `item` (a focus item) inside an item with objectName `name`?"""
    while item is not None:
        if item.objectName() == name:
            return True
        item = item.parentItem()
    return False


def tree(item):
    """Every item under `item` by the item tree (a view's delegates are not QObject children)."""
    for child in item.childItems():
        yield child
        yield from tree(child)


def wheel(root, point, up=True):
    event = QWheelEvent(QPointF(point), QPointF(point), QPoint(0, 0), QPoint(0, 120 if up else -120),
                        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QCoreApplication.sendEvent(root, event)


def open_drawer(root):
    panel = visible(root, 'conversationPanel')
    QMetaObject.invokeMethod(panel, 'openDrawer')
    assert pump(1, lambda: panel.property('drawerOpen'))
    pump(0.45)                                 # the slide has finished
    return panel


def close_drawer(root, panel):
    if panel.property('drawerOpen'):
        QMetaObject.invokeMethod(panel, 'closeDrawer')
    assert pump(1, lambda: not panel.property('drawerOpen'))
    pump(0.45)


class WindowTest(unittest.TestCase):
    def test_drawer_opens_lists_and_escape_closes_only_it(self):
        root, controller, messages = window()
        panel = visible(root, 'conversationPanel')
        root.setProperty('sheet', 'home')
        pump(0.2)
        QMetaObject.invokeMethod(panel, 'openDrawer')
        self.assertTrue(pump(1, lambda: panel.property('drawerOpen')))
        threads = visible(root, 'chatThreads')
        self.assertTrue(pump(1, lambda: threads.property('count') == 5))
        search = visible(root, 'chatSearch')
        self.assertTrue(pump(1, lambda: search.property('activeFocus')))
        QTest.keyClick(root, Qt.Key_Escape)
        self.assertTrue(pump(1, lambda: not panel.property('drawerOpen')))
        self.assertEqual(root.property('sheet'), 'home')     # Escape closed the drawer, not the page
        root.setProperty('sheet', '')
        pump(0.2)
        mine = [m for m in messages if any(n in m for n in ('ConversationPanel', 'MessageDelegate', 'CommandDock'))]
        self.assertEqual(mine, [])

    def test_composer_enter_sends_shift_enter_breaks_and_ime_keeps_its_word(self):
        root, controller, messages = window()
        field = visible(root, 'composer')
        QMetaObject.invokeMethod(field, 'forceActiveFocus')
        pump(0.1)
        for ch in 'hello':
            QTest.keyClick(root, ch)
        QTest.keyClick(root, Qt.Key_Return, Qt.ShiftModifier)
        for ch in 'world':
            QTest.keyClick(root, ch)
        self.assertEqual(field.property('text'), 'hello\nworld')
        self.assertEqual(controller.sent, [])
        QTest.keyClick(root, Qt.Key_Return)
        self.assertEqual(controller.sent, ['hello\nworld'])
        self.assertEqual(field.property('text'), '')
        # while an input method composes a word, Enter is the input method's, never a send
        field.setProperty('text', 'اسألي')
        field.setProperty('cursorPosition', 5)
        QCoreApplication.sendEvent(field, QInputMethodEvent('ميرا', []))
        pump(0.05)
        self.assertTrue(field.property('inputMethodComposing'))
        QTest.keyClick(root, Qt.Key_Return)
        QTest.keyClick(root, Qt.Key_Enter)
        self.assertEqual(controller.sent, ['hello\nworld'])
        commit = QInputMethodEvent('', [])
        commit.setCommitString('ميرا')
        QCoreApplication.sendEvent(field, commit)
        pump(0.05)
        self.assertFalse(field.property('inputMethodComposing'))
        self.assertIn('ميرا', field.property('text'))
        field.setProperty('text', 'ميرا')
        QTest.keyClick(root, Qt.Key_Enter)                     # the keypad Enter sends as well
        self.assertEqual(controller.sent, ['hello\nworld', 'ميرا'])

    def test_composer_grows_to_five_lines_then_scrolls(self):
        root, controller, messages = window()
        field = visible(root, 'composer')
        bar = visible(root, 'composerBar')
        view = visible(root, 'composerView')
        dock = visible(root, 'commandDock')
        field.setProperty('text', '')
        pump(0.4)
        single = bar.property('height')
        self.assertEqual(single, 72)
        base = dock.property('height')
        field.setProperty('text', 'one line')
        pump(0.3)
        self.assertEqual(bar.property('height'), single)
        field.setProperty('text', 'a\nb\nc')
        pump(0.4)
        three = bar.property('height')
        self.assertGreater(three, single)
        field.setProperty('text', '\n'.join(str(i) for i in range(12)))
        pump(0.4)
        tall = bar.property('height')
        self.assertGreater(tall, three)
        self.assertLess(view.property('height'), field.property('implicitHeight'))   # the rest scrolls
        field.setProperty('text', '\n'.join(str(i) for i in range(30)))
        pump(0.4)
        self.assertEqual(bar.property('height'), tall)          # capped at five lines
        # the bar grows upward over the content: the dock (and so Mira's stage above it) never moves
        self.assertEqual(dock.property('height'), base)
        self.assertEqual(dock.property('growth'), tall - single)
        field.setProperty('text', '')
        pump(0.4)
        self.assertEqual(bar.property('height'), single)
        self.assertEqual(dock.property('growth'), 0)

    def test_entries_added_in_a_row_leave_no_gaps(self):
        root, controller, messages = window()
        controller.chat.clear()
        pump(0.2)
        for role, text, status in [('user', 'ميرا، كم ضوء مضاء الآن؟', ''), ('action', 'أضواء البيت · المضاء 2', 'ok'),
                                   ('mira', 'في ضوءان مضاءان الآن: المكتب باللون الوردي ومصباح الطاولة. بدك أطفيهم؟', ''),
                                   ('user', 'كيف أعرف نسخة النظام؟', ''),
                                   ('mira', 'شغّل هذا:\n\n```bash\n# اعرض النشر\nbootc status\n```\n\nوبعدها تظهر النسخة.', '')]:
            controller._add(role, text, status=status, persist=False)
        pump(1.0)
        chat = visible(root, 'chatList')
        entries = sorted((i for i in chat.property('contentItem').childItems() if i.property('role')),
                         key=lambda i: i.property('y'))
        self.assertEqual(len(entries), 5)
        for above, below in zip(entries, entries[1:]):
            self.assertAlmostEqual(below.property('y'), above.property('y') + above.property('height') + chat.property('spacing'),
                                   delta=0.5, msg=above.property('text'))
        cards = [o for o in tree(entries[-1]) if o.objectName() == 'codeCard' and o.property('visible')]
        self.assertEqual(len(cards), 1)                          # the code block is its own card
        copy = next(o for o in tree(cards[0]) if o.objectName() == 'copyCode')
        controller.copied.clear()
        QMetaObject.invokeMethod(copy, 'click')
        self.assertEqual(controller.copied, ['# اعرض النشر\nbootc status'])   # only the code
        controller.chat.clear()

    def test_delegate_height_is_settled_outside_the_listview_layout_binding(self):
        """An entry's height passes through wrong values while it is made (a reply measured 1208 px,
        then 452). Bound to the view, those made the ListView release and remake its entries for
        ever: one core, 30 MiB a second, 8.9 GiB at the OOM kill on the Oracle A1. The height is
        state, written only by a deferred measurement."""
        qml = (ROOT / 'qml' / 'Mira' / 'MessageDelegate.qml').read_text(encoding='utf-8')
        self.assertIn('property real settledHeight:', qml)
        self.assertIn('height: settledHeight', qml)
        self.assertIn('Qt.callLater(settleHeight)', qml)
        self.assertIn('onWidthChanged: Qt.callLater(settleHeight)', qml)
        self.assertIn('onNewDayChanged: Qt.callLater(settleHeight)', qml)
        self.assertNotRegex(qml, r'(?m)^\s*height:\s*sep\.height\s*\+\s*body\.height',
                            'delegate height is bound back into ListView geometry again')
        # every writer of the height is deferred: an immediate one is the binding by another name
        for line in qml.splitlines():
            if 'settleHeight' in line and 'function settleHeight' not in line:
                self.assertIn('Qt.callLater(', line, line.strip())

    def test_an_entry_keeps_the_height_of_what_it_draws(self):
        """A height measured once is wrong the first time the entry changes. «Try again» leaves an
        error card when the next message arrives; the first version of the settled height kept
        the button's row, a 34 px gap under the card."""
        root, controller, messages = window()
        controller.chat.clear()
        controller.chat.append({'role': 'user', 'text': 'q'})
        controller.chat.append({'role': 'mira', 'text': 'a long reply that wraps. ' * 30})
        controller.chat.append({'role': 'user', 'text': 'q2'})
        controller.chat.append({'role': 'error', 'text': 'offline', 'status': 'error'})
        pump(0.6)
        chat = visible(root, 'chatList')

        def entries():
            found = [i for i in tree(chat) if i.property('settledHeight') is not None
                     and i.property('role') is not None]
            return sorted(found, key=lambda i: i.property('index'))

        def drawn(entry):       # sep + body + the entry's margins, read from the items themselves
            return max(child.y() + child.height() for child in entry.childItems()) + 7

        def settled():
            return all(abs(e.height() - drawn(e)) < 1.5 for e in entries())

        self.assertTrue(pump(1, lambda: len(entries()) == 4 and settled()),
                        [(e.property('role'), e.height(), drawn(e)) for e in entries()])
        card = entries()[-1]
        self.assertTrue(card.property('canRetry'), 'the lone error must offer «Try again»')
        with_button = card.height()
        controller.chat.append({'role': 'user', 'text': 'again'})
        self.assertTrue(pump(1, lambda: not card.property('canRetry') and settled()),
                        f'the error card kept {card.height()} px for {drawn(card)} px of content')
        self.assertLess(card.height(), with_button, 'the row of the button was not given back')
        self.assertEqual([m for m in messages if 'MessageDelegate' in m], [])
        controller.chat.clear()

    def test_the_open_drawer_keeps_every_click_wheel_and_tab(self):
        root, controller, messages = window()
        controller.chat.clear()
        for i in range(14):
            controller._add('user', f'سؤال رقم {i} ' + 'كلام ' * 8, persist=False)
            controller._add('mira', f'جواب رقم {i} ' + 'نص طويل ' * 12, persist=False)
        pump(0.6)
        chat = visible(root, 'chatList')
        panel = open_drawer(root)
        try:
            self.assertFalse(chat.property('enabled'))
            threads = visible(root, 'chatThreads')
            top, box = scene_rect(threads), scene_rect(panel)
            spots = [QPoint(int(box.left() + 40), int(top.top() - 22)),            # beside the All/Archived pills
                     QPoint(int(box.right() - 40), int(top.top() - 22)),
                     QPoint(int(top.center().x()), int(top.bottom() - 30)),         # below the last chat
                     QPoint(int(box.center().x()), int(box.top() + 30))]           # the drawer's title row
            controller.copied.clear()
            y = chat.property('contentY')
            for spot in spots:
                QTest.mouseClick(root, Qt.RightButton, Qt.NoModifier, spot)
                wheel(root, spot)
                pump(0.05)
            pump(0.2)
            self.assertEqual(controller.copied, [])              # nothing under the drawer was reached
            self.assertEqual(chat.property('contentY'), y)       # nor scrolled
            # the keyboard stays out of the hidden conversation too
            QMetaObject.invokeMethod(visible(root, 'chatSearch'), 'forceActiveFocus')
            for key, modifier in [(Qt.Key_Backtab, Qt.ShiftModifier)] * 6 + [(Qt.Key_Tab, Qt.NoModifier)] * 14:
                QTest.keyClick(root, key, modifier)
                pump(0.02)
                self.assertFalse(inside(root.activeFocusItem(), 'chatList'), 'Tab reached a hidden message')
        finally:
            close_drawer(root, panel)
        self.assertTrue(chat.property('enabled'))
        # with the drawer closed a right-click copies again (the gate above can fail)
        entry = QPoint(int(scene_rect(chat).center().x()), int(scene_rect(chat).bottom() - 40))
        QTest.mouseClick(root, Qt.RightButton, Qt.NoModifier, entry)
        pump(0.1)
        self.assertEqual(len(controller.copied), 1)
        controller.chat.clear()

    def test_drawer_arrow_keys_walk_the_chats_and_return_opens_one(self):
        root, controller, messages = window()
        history = controller.chatHistory
        history.opened.clear()
        panel = open_drawer(root)
        search = visible(root, 'chatSearch')
        self.assertTrue(pump(1, lambda: search.property('activeFocus')))
        QTest.keyClick(root, Qt.Key_Down)
        self.assertEqual(root.activeFocusItem().objectName(), 'chatThreadRow')
        QTest.keyClick(root, Qt.Key_Up)                         # from the first chat back to the search
        self.assertTrue(search.property('activeFocus'))
        QTest.keyClick(root, Qt.Key_Down)
        QTest.keyClick(root, Qt.Key_Down)
        QTest.keyClick(root, Qt.Key_Down)
        QTest.keyClick(root, Qt.Key_Up)
        self.assertEqual(root.activeFocusItem().objectName(), 'chatThreadRow')
        QTest.keyClick(root, Qt.Key_Return)
        self.assertEqual(history.opened, ['r2'])                # the second chat of the review list
        self.assertTrue(pump(1, lambda: not panel.property('drawerOpen')))
        pump(0.45)

    def test_typing_in_the_drawer_search_filters_the_chats(self):
        root, controller, messages = window()
        history = controller.chatHistory
        try:
            with private_chats() as m, patch.object(chat_ui, 'TEST_MODE', False):
                m.add_message('user', 'أين إعدادات الصوت؟')
                m.new_thread()
                m.add_message('user', 'Install VLC please')
                panel = open_drawer(root)                        # opening reads the chats (live here)
                threads = visible(root, 'chatThreads')
                self.assertTrue(pump(3, lambda: threads.property('count') == 2))
                for ch in 'vlc':
                    QTest.keyClick(root, ch)
                self.assertTrue(pump(3, lambda: threads.property('count') == 1))
                self.assertEqual(history.threads.rows()[0]['title'], 'Install VLC please')
                QTest.keyClick(root, Qt.Key_Escape)              # closes the drawer and clears the search
                self.assertTrue(pump(1, lambda: not panel.property('drawerOpen')))
                self.assertTrue(pump(3, lambda: history.state['query'] == '' and not history.state['loading']))
                pump(0.3)
        finally:
            history.update(query='', archived=False, loading=False, error='')
            history.review()

    def test_prefill_puts_the_cursor_after_the_words(self):
        root, controller, messages = window()
        field = visible(root, 'composer')
        field.setProperty('text', '')
        controller.prefill.emit('ثبّتي لي VLC')
        self.assertTrue(pump(1, lambda: field.property('activeFocus') and field.property('cursorPosition') == 12))
        QTest.keyClick(root, 'x')
        self.assertEqual(field.property('text'), 'ثبّتي لي VLCx')    # the owner continues after the words
        field.setProperty('text', '')

    def test_an_attachment_over_the_limit_disables_send_and_says_why(self):
        root, controller, messages = window()
        dock = visible(root, 'commandDock')
        field = visible(root, 'composer')
        send = visible(root, 'sendButton')
        words = i18n.table(controller.property('lang'))
        sent = list(controller.sent)
        try:
            field.setProperty('text', 'لخّصي الملف')
            dock.setProperty('attachmentName', 'notes.txt')
            dock.setProperty('attachmentText', 'a' * 7000)
            pump(0.3)
            self.assertTrue(dock.property('tooLong'))
            self.assertEqual(dock.property('composedLength'), len('لخّصي الملف') + 2 + len('[notes.txt]\n') + 7000)
            self.assertFalse(send.property('enabled'))
            counter = visible(root, 'composerCounterText')
            self.assertIn(words['ch_too_long_file'], counter.property('text'))
            self.assertIn(f"{dock.property('composedLength')} / 6000", counter.property('text'))
            # the count sits on the bar's edge, clear of the buttons inside the bar
            pill = scene_rect(visible(root, 'composerCounter'))
            self.assertFalse(pill.intersects(scene_rect(send)))
            self.assertLessEqual(pill.bottom(), scene_rect(visible(root, 'composerBar')).top())
            self.assertFalse(pill.intersects(scene_rect(visible(root, 'attachmentChip'))))
            QMetaObject.invokeMethod(field, 'forceActiveFocus')
            pump(0.05)
            QTest.keyClick(root, Qt.Key_Return)
            self.assertEqual(controller.sent, sent)                 # kept, not sent
            self.assertTrue(dock.property('refused'))
            dock.setProperty('attachmentText', 'a' * 100)           # a smaller file goes
            pump(0.1)
            self.assertTrue(send.property('enabled'))
            self.assertFalse(visible(root, 'composerBar').property('visible') is False)
            field.setProperty('text', 'x' * 6001)                   # the typed words alone: the plain reason
            dock.setProperty('attachmentName', '')
            dock.setProperty('attachmentText', '')
            pump(0.1)
            self.assertIn(words['ch_too_long'], visible(root, 'composerCounterText').property('text'))
            self.assertNotIn(words['ch_too_long_file'], visible(root, 'composerCounterText').property('text'))
        finally:
            field.setProperty('text', '')
            dock.setProperty('attachmentName', '')
            dock.setProperty('attachmentText', '')
            pump(0.1)

    def test_day_separators_follow_a_language_switch(self):
        root, controller, messages = window()
        controller.chat.clear()
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        controller._add('user', 'أمس', persist=False, day=yesterday)
        controller._add('user', 'اليوم', persist=False)
        pump(0.4)
        lang = controller.property('lang')
        try:
            controller.setLang('ar')
            pump(0.2)
            texts = lambda: {o.property('text') for o in tree(root.contentItem())
                             if o.objectName() == 'dayChipText' and o.property('visible')}
            self.assertIn('أمس', texts())
            controller.setLang('en')
            self.assertTrue(pump(1, lambda: 'Yesterday' in texts()))
        finally:
            controller.setLang(lang)
            controller.chat.clear()
            pump(0.2)


if __name__ == '__main__':
    unittest.main()
