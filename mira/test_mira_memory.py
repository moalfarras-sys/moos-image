"""Local persistence stays readable, private and chat-scoped, and does not grant capabilities."""
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mira_memory


class MemoryTest(unittest.TestCase):
    def test_profile_and_conversation_survive_reload(self):
        with tempfile.TemporaryDirectory() as temp:
            old=os.environ.get('XDG_CONFIG_HOME')
            os.environ['XDG_CONFIG_HOME']=temp
            memory=importlib.reload(mira_memory)
            try:
                memory.save_profile('طوّرت ميرا مع MoOS. مشروعي هو مساعد منزلي.')
                memory.remember_fact('اسمي محمد')
                memory.remember_fact('اسمي محمد')
                self.assertEqual(memory.profile_text().count('اسمي محمد'),1)
                self.assertIn('مساعد منزلي',memory.profile_text())
                with self.assertRaises(ValueError):memory.remember_fact('x'*501)
                memory.add_message('user','مرحبا ميرا')
                memory.add_message('mira','أهلاً بك')
                memory.add_message('action','حدث التنفيذ')
                self.assertIn('MoOS',memory.profile_text())
                self.assertEqual([m['role'] for m in memory.recent_messages()],['user','mira'])
                memory.add_message('user','كم ضوء عندي؟')
                memory.add_message('mira','يوجد ')
                memory.add_message('mira','ضوءان.')
                history=memory.recent_messages(3)
                self.assertEqual([m['role'] for m in history],['mira','user','mira'])
                self.assertEqual(history[-1]['text'],'يوجد ضوءان.')
                self.assertEqual(Path(memory.PROFILE).stat().st_mode & 0o777,0o600)
                self.assertEqual(Path(memory.CONVERSATION).stat().st_mode & 0o777,0o600)
            finally:
                if old is None:os.environ.pop('XDG_CONFIG_HOME',None)
                else:os.environ['XDG_CONFIG_HOME']=old
                importlib.reload(mira_memory)


class ThreadTest(unittest.TestCase):
    """Chats: the model sees only the open one; old data needs no migration; nothing is destroyed."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get('XDG_CONFIG_HOME')
        os.environ['XDG_CONFIG_HOME'] = self.temp.name
        self.m = importlib.reload(mira_memory)

    def tearDown(self):
        if self.old is None:
            os.environ.pop('XDG_CONFIG_HOME', None)
        else:
            os.environ['XDG_CONFIG_HOME'] = self.old
        importlib.reload(mira_memory)
        self.temp.cleanup()

    def legacy(self, *rows):
        """Records as the app wrote them before chats existed (no thread, no id)."""
        self.m.DIR.mkdir(parents=True, exist_ok=True)
        with open(self.m.CONVERSATION, 'a', encoding='utf-8') as stream:
            for i, (role, text) in enumerate(rows):
                stream.write(json.dumps({'time': f'2026-09-20T10:00:{i:02d}.000000+00:00', 'role': role, 'text': text},
                                        ensure_ascii=False) + '\n')

    def test_legacy_rows_are_the_default_chat_without_migration(self):
        self.legacy(('user', 'كم الساعة؟'), ('mira', 'العاشرة.'), ('action', 'قديم بلا حالة'))
        before = self.m.CONVERSATION.read_bytes()
        self.assertEqual(self.m.current_thread(), 'main')
        self.assertEqual([r['text'] for r in self.m.recent_messages()], ['كم الساعة؟', 'العاشرة.'])
        # an old action's outcome is unknown: it is never shown as a result
        self.assertEqual([r['role'] for r in self.m.messages()], ['user', 'mira'])
        threads = self.m.list_threads()
        self.assertEqual([(t['id'], t['title'], t['count']) for t in threads], [('main', 'كم الساعة؟', 3)])
        self.m.add_message('user', 'وبعدين؟')
        self.assertTrue(self.m.CONVERSATION.read_bytes().startswith(before))   # appended to, never rewritten
        self.assertEqual(len(self.m.recent_messages()), 3)

    def test_a_new_chat_stops_feeding_old_turns_and_can_be_reopened(self):
        self.legacy(('user', 'سؤال قديم'), ('mira', 'جواب قديم'))
        first = self.m.current_thread()
        fresh = self.m.new_thread()
        self.assertNotEqual(fresh, first)
        self.assertEqual(self.m.recent_messages(), [])
        self.assertEqual(self.m.new_thread(), fresh)            # an empty open chat is reused, not multiplied
        self.m.add_message('user', 'سؤال جديد')
        self.m.add_message('mira', 'جواب جديد')
        self.assertEqual([r['text'] for r in self.m.recent_messages()], ['سؤال جديد', 'جواب جديد'])
        self.m.open_thread(first)
        self.assertEqual([r['text'] for r in self.m.recent_messages()], ['سؤال قديم', 'جواب قديم'])
        self.assertEqual([r['text'] for r in self.m.messages(fresh)], ['سؤال جديد', 'جواب جديد'])
        with self.assertRaises(ValueError):
            self.m.open_thread('nope-404')
        with self.assertRaises(ValueError):
            self.m.open_thread('../../etc')
        self.assertEqual(Path(self.m.THREADS).stat().st_mode & 0o777, 0o600)

    def test_list_names_orders_pins_and_archives(self):
        self.m.add_message('user', 'الأولى\n[notes.txt]\nمحتوى ملف طويل')
        a = self.m.current_thread()
        b = self.m.new_thread()
        self.m.add_message('user', 'x' * 90)
        c = self.m.new_thread()        # open and empty: listed while it is open
        rows = self.m.list_threads()
        self.assertEqual([r['id'] for r in rows], [c, b, a])
        self.assertEqual(rows[2]['title'], 'الأولى')            # the first line only, not the attached file
        self.assertTrue(rows[1]['title'].endswith('…') and len(rows[1]['title']) == 60)
        self.assertTrue(rows[0]['current'] and rows[0]['count'] == 0)
        self.m.pin_thread(a, True)
        self.m.rename_thread(b, '  خطة   المشروع ')
        rows = self.m.list_threads()
        self.assertEqual(rows[0]['id'], a)
        self.assertEqual(next(r for r in rows if r['id'] == b)['title'], 'خطة المشروع')
        self.m.rename_thread(b, '')                              # the automatic name comes back
        self.assertTrue(next(r for r in self.m.list_threads() if r['id'] == b)['title'].startswith('xxx'))
        with self.assertRaises(ValueError):
            self.m.rename_thread(b, 'y' * 81)
        with self.assertRaises(ValueError):
            self.m.rename_thread(b, 'a\x07b')
        with self.assertRaises(ValueError):
            self.m.pin_thread('missing', True)
        self.m.archive_thread(b, True)
        self.assertNotIn(b, [r['id'] for r in self.m.list_threads()])
        self.assertIn(b, [r['id'] for r in self.m.list_threads(include_archived=True) if r['archived']])
        self.m.open_thread(b)
        self.m.add_message('user', 'رجعت')                      # talking in it again brings it back
        self.assertIn(b, [r['id'] for r in self.m.list_threads()])
        self.m.open_thread(a)
        self.assertNotIn(c, [r['id'] for r in self.m.list_threads()])   # empty and closed: not listed

    def test_actions_keep_their_verified_status(self):
        self.m.add_message('user', 'شغّلي الضوء')
        self.m.add_message('action', 'تأكدت: الضوء يعمل', status='ok', title='home_control', tool='home_control')
        self.m.add_message('error', 'تعذّر الاتصال')
        rows = self.m.messages()
        self.assertEqual([(r['role'], r['status']) for r in rows], [('user', ''), ('action', 'ok'), ('error', 'error')])
        self.assertEqual(rows[1]['tool'], 'home_control')
        self.assertEqual([r['role'] for r in self.m.recent_messages()], ['user'])   # the model gets words only
        self.assertEqual(self.m.add_message('user', '   '), '')
        self.assertEqual(self.m.add_message('root', 'x'), '')

    def test_regenerate_retracts_only_a_plain_reply(self):
        self.m.add_message('user', 'اشرحي لي bootc')
        self.m.add_message('mira', 'bootc هو ')
        self.m.add_message('mira', 'نظام صور.')
        self.assertEqual(self.m.retract_last_reply(), 'اشرحي لي bootc')
        self.assertEqual([r['role'] for r in self.m.recent_messages()], ['user'])
        self.assertEqual([r['role'] for r in self.m.messages()], ['user'])
        self.assertEqual(self.m.retract_last_reply(), '')      # nothing left to retract
        self.m.add_message('mira', 'جواب جديد')
        self.assertEqual([r['text'] for r in self.m.recent_messages()], ['اشرحي لي bootc', 'جواب جديد'])
        # a turn that acted is never offered again
        self.m.add_message('user', 'أطفئي الأضواء')
        self.m.add_message('action', 'أطفأت 3 أضواء', status='ok')
        self.m.add_message('mira', 'تم.')
        size = self.m.CONVERSATION.stat().st_size
        self.assertEqual(self.m.retract_last_reply(), '')
        self.assertEqual(self.m.CONVERSATION.stat().st_size, size)
        self.assertEqual(self.m.list_threads()[0]['count'], 5)  # the retracted pieces are not counted

    def test_only_the_models_plain_words_are_taken_back(self):
        # a fired reminder after the answer: the turn is left alone
        self.m.add_message('user', 'ما هو bootc؟')
        self.m.add_message('mira', 'نظام صور.')
        self.m.add_message('mira', '⏰ استرح', tool='reminder')
        size = self.m.CONVERSATION.stat().st_size
        self.assertEqual(self.m.retract_last_reply(), '')
        self.assertEqual(self.m.CONVERSATION.stat().st_size, size)
        self.assertEqual([r['text'] for r in self.m.messages()], ['ما هو bootc؟', 'نظام صور.', '⏰ استرح'])
        # the window's own answer to a waiting card («لا» cancelled it): never sent to the model as a question
        self.m.add_message('user', 'لا')
        self.m.add_message('mira', 'تمام، ألغيته وما نفّذت شي.', tool='cards')
        self.assertEqual(self.m.retract_last_reply(), '')
        self.assertFalse(self.m.plain_reply({'role': 'mira', 'tool': 'cards'}))
        self.assertTrue(self.m.plain_reply({'role': 'mira', 'tool': ''}))

    def test_a_question_that_got_only_an_error_is_asked_again_without_hiding_it(self):
        self.m.add_message('user', 'كم الساعة؟')
        self.m.add_message('error', 'تعذّر الاتصال', status='error')
        size = self.m.CONVERSATION.stat().st_size
        self.assertEqual(self.m.retract_last_reply(), 'كم الساعة؟')
        self.assertEqual(self.m.CONVERSATION.stat().st_size, size)          # nothing hidden: the error happened
        self.assertEqual([r['role'] for r in self.m.messages()], ['user', 'error'])
        # words and an error mixed after the question: left as it is
        self.m.add_message('mira', 'الساعة ')
        self.m.add_message('error', 'انقطع الاتصال', status='error')
        self.assertEqual(self.m.retract_last_reply(), '')

    def test_a_long_question_and_an_unsupported_result_survive_reopening(self):
        question = 'س' * 5000
        self.m.add_message('user', question)
        self.m.add_message('action', 'هذا الجهاز لا يدعم التحكم بالسطوع', status='unsupported', tool='screen_brightness')
        rows = self.m.messages()
        self.assertEqual(len(rows[0]['text']), 5000)
        self.assertEqual((rows[1]['role'], rows[1]['status']), ('action', 'unsupported'))
        self.m.add_message('user', 'x' * 7000)
        self.assertEqual(len(self.m.messages()[-1]['text']), self.m.TEXT_MAX)   # what the composer accepts

    def test_a_late_result_does_not_bring_an_archived_chat_back(self):
        self.m.add_message('user', 'ثبّتي VLC')
        first = self.m.current_thread()
        self.m.new_thread()
        self.m.archive_thread(first, True)
        self.m.add_message('action', 'اكتمل تثبيت VLC', status='ok', tool='moai', thread=first)
        self.assertNotIn(first, [r['id'] for r in self.m.list_threads()])
        self.assertEqual(self.m.messages(first)[-1]['text'], 'اكتمل تثبيت VLC')
        self.assertEqual(self.m.messages(), [])                                  # not in the open chat
        self.m.open_thread(first)
        self.m.add_message('user', 'شكراً')                                     # the owner talks there again
        self.assertIn(first, [r['id'] for r in self.m.list_threads()])

    def test_a_missing_chat_is_its_own_error(self):
        with self.assertRaises(self.m.ThreadNotFound):
            self.m.open_thread('nope-404')
        with self.assertRaises(self.m.ThreadNotFound):
            self.m.pin_thread('nope-404', True)
        self.assertTrue(issubclass(self.m.ThreadNotFound, ValueError))

    def test_search_ignores_case_diacritics_and_letter_forms(self):
        self.m.add_message('user', 'أين إعدادات الصوت؟')
        first = self.m.current_thread()
        self.m.new_thread()
        self.m.add_message('user', 'Install VLC please')
        self.m.add_message('mira', 'جهّزتُ تثبيت VLC وينتظر موافقتك.')
        second = self.m.current_thread()
        self.m.rename_thread(first, 'Sound settings')
        self.assertEqual([r['id'] for r in self.m.search_threads('اعدادات')], [first])
        self.assertEqual([r['id'] for r in self.m.search_threads('vlc')], [second])
        hit = self.m.search_threads('جهزت')[0]
        self.assertIn('جهّزتُ', hit['snippet'])
        self.assertEqual([r['id'] for r in self.m.search_threads('sound SETTINGS')], [first])   # by its name
        self.assertEqual(self.m.search_threads('   '), [])
        self.assertEqual(self.m.search_threads('غير موجود'), [])

    def test_a_damaged_index_never_hides_the_conversation(self):
        self.legacy(('user', 'مرحبا'), ('mira', 'أهلاً'))
        self.m.THREADS.write_text('{not json', encoding='utf-8')
        self.assertEqual(self.m.current_thread(), 'main')
        self.assertEqual(len(self.m.recent_messages()), 2)
        with open(self.m.CONVERSATION, 'ab') as stream:
            stream.write(b'garbage line\n\xff\xfe\n')
        self.assertEqual(len(self.m.recent_messages()), 2)
        self.assertEqual(self.m.list_threads()[0]['count'], 2)

    def test_a_damaged_index_is_set_aside_and_the_newest_chat_stays_open(self):
        self.m.add_message('user', 'أول')
        self.m.new_thread()
        self.m.add_message('user', 'ثاني')
        second = self.m.current_thread()
        self.m.THREADS.write_bytes(b'\xff{"current": broken')
        self.assertEqual(self.m.current_thread(), second)           # the chat written to last
        aside = list(self.m.THREADS.parent.glob('mira-threads.json.damaged-*'))
        self.assertEqual(len(aside), 1)
        self.assertEqual(aside[0].read_bytes(), b'\xff{"current": broken')   # kept for the owner, never overwritten
        self.assertEqual(json.loads(self.m.THREADS.read_text())['current'], second)
        self.assertEqual(Path(self.m.THREADS).stat().st_mode & 0o777, 0o600)
        self.m.THREADS.write_text('[]', encoding='utf-8')             # valid JSON, not an index: damaged too
        self.m.current_thread()
        self.assertEqual(len(list(self.m.THREADS.parent.glob('mira-threads.json.damaged-*'))), 2)

    @unittest.skipIf(os.geteuid() == 0, 'root reads a 000 file')
    def test_an_unreadable_index_is_never_overwritten(self):
        self.m.add_message('user', 'سؤال')
        self.m.rename_thread(self.m.current_thread(), 'خطة')
        before = self.m.THREADS.read_bytes()
        os.chmod(self.m.THREADS, 0)
        try:
            self.assertNotEqual(self.m.add_message('user', 'ما زال يُحفظ'), '')   # the words are still kept
            with self.assertRaises(OSError):
                self.m.new_thread()
            with self.assertRaises(OSError):
                self.m.pin_thread('main', True)
        finally:
            os.chmod(self.m.THREADS, 0o600)
        self.assertEqual(self.m.THREADS.read_bytes(), before)
        self.assertEqual(list(self.m.THREADS.parent.glob('mira-threads.json.damaged-*')), [])

    def test_trimming_keeps_pinned_chats(self):
        self.m.add_message('user', 'خطة مهمة')
        pinned = self.m.current_thread()
        self.m.pin_thread(pinned, True)
        self.m.new_thread()
        with patch.object(self.m, 'MAX_BYTES', 4000), patch.object(self.m, 'KEEP_BYTES', 1500), \
                patch.object(self.m, 'PINNED_BYTES', 1000):
            for i in range(60):
                self.m.add_message('user', f'رسالة رقم {i}')
            self.assertLess(self.m.CONVERSATION.stat().st_size, 4000)
        self.assertEqual([r['text'] for r in self.m.messages(pinned)], ['خطة مهمة'])
        self.assertEqual(self.m.recent_messages(1)[0]['text'], 'رسالة رقم 59')
        self.assertEqual(Path(self.m.CONVERSATION).stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
