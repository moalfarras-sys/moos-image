"""Tests for Mira's system-control modules: pending, desktop_tools, reminders, routines, announce.

Runs offline (no network) and never reads the owner's desktop by default. Three live, read-only
checks (media status, the clipboard, the window list) run only when asked for explicitly with
MIRA_LIVE_TESTS=1 on a desktop session: a test must not touch the owner's live desktop (AGENTS.md),
and the clipboard can hold anything he copied. Nothing here runs a destructive command; the only
shell-ish thing is a temp-dir `os.scandir` via find_files.

    /var/home/moos/.local/share/mira/venv/bin/python -m unittest test_systools -v
    MIRA_LIVE_TESTS=1 /var/home/moos/.local/share/mira/venv/bin/python -m unittest test_systools.DesktopLive -v
"""
import asyncio
import os
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import announce
import desktop_tools
import pending
import reminders
import routines


def _has_session() -> bool:
    return bool(os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DBUS_SESSION_BUS_ADDRESS')
                or Path(f'/run/user/{os.getuid()}/bus').exists())


def _live_tests_asked() -> bool:
    """Only an explicit MIRA_LIVE_TESTS=1 lets a test read the owner's running desktop."""
    return os.environ.get('MIRA_LIVE_TESTS') == '1'


# ─── pending.is_confirmation ──────────────────────────────────────────
class ConfirmationStrictness(unittest.TestCase):
    def test_yes_words(self):
        for text in ['نعم', 'أيوه', 'ايوا', 'اكيد', 'أكّد', 'موافق', 'نفّذ', 'تمام نفّذ',
                     'نعم نفذ', 'yes', 'confirm', 'do it', 'yes please', 'يا ميرا نعم', 'أكيد نفذ']:
            self.assertEqual(pending.is_confirmation(text), 'yes', text)

    def test_no_words(self):
        for text in ['لا', 'لأ', 'الغي', 'إلغاء', 'ألغِ', 'no', 'cancel', 'nope',
                     "don't do it", 'no thanks', 'لا لا', 'يا ميرا لا']:
            self.assertEqual(pending.is_confirmation(text), 'no', text)

    def test_embedded_word_is_not_a_confirmation(self):
        # The trigger word appears inside a longer, unrelated sentence.
        for text in ['نعم الساعة كم؟', 'نعم كم الوقت الآن', 'لا أعرف كم الساعة',
                     'نعم أريد أن أعرف الطقس في دبي اليوم', 'yes what time is it',
                     'no I was asking about the weather today please', 'أيوه بس شو الأخبار']:
            self.assertIsNone(pending.is_confirmation(text), text)

    def test_mixed_and_empty(self):
        for text in ['لا نعم', 'نعم لا', '', '   ', 'ميرا', 'يا ميرا', 'تمام', 'شكرا', 'ok']:
            self.assertIsNone(pending.is_confirmation(text), text)

    def test_length_cap(self):
        self.assertIsNone(pending.is_confirmation('نعم نعم نعم نعم نعم'))  # >4 words


# ─── PendingActions ───────────────────────────────────────────────────
class PendingStore(unittest.TestCase):
    def setUp(self):
        self.now = [1000.0]
        self.p = pending.PendingActions(clock=lambda: self.now[0])

    def test_add_returns_public_view_without_payload(self):
        card = self.p.add('close_window', 'إغلاق', 'Close', 'konsole', {'tool': 'close_window'})
        self.assertNotIn('payload', card)
        self.assertEqual(card['kind'], 'close_window')
        self.assertIn('id', card)

    def test_take_is_one_shot_and_returns_payload(self):
        card = self.p.add('x_kind', 'ع', 'e', '', {'secret': 42})
        got = self.p.take(card['id'])
        self.assertEqual(got['payload'], {'secret': 42})
        self.assertIsNone(self.p.take(card['id']))          # second take: gone

    def test_expiry(self):
        card = self.p.add('x_kind', 'ع', 'e', '', {}, ttl=60)
        self.now[0] += 61
        self.assertIsNone(self.p.take(card['id']))
        self.assertIsNone(self.p.get(card['id']))
        self.assertEqual(self.p.list(), [])

    def test_latest_and_reject(self):
        a = self.p.add('k_a', 'ا', 'a', '', {})
        self.now[0] += 1
        b = self.p.add('k_b', 'ب', 'b', '', {})
        self.assertEqual(self.p.latest()['id'], b['id'])
        self.assertEqual(self.p.reject(a['id'])['id'], a['id'])
        self.assertEqual(len(self.p.list()), 1)

    def test_ttl_bounds(self):
        with self.assertRaises(ValueError):
            self.p.add('k', 'ا', 'a', '', {}, ttl=0)
        with self.assertRaises(ValueError):
            self.p.add('k', 'ا', 'a', '', {}, ttl=99999)

    def test_bad_kind(self):
        with self.assertRaises(ValueError):
            self.p.add('Bad Kind', 'ا', 'a', '', {})

    def test_respond_single_yes_takes_it(self):
        card = self.p.add('k', 'ا', 'a', '', {'go': 1})
        out = self.p.respond('نعم')
        self.assertEqual(out['verdict'], 'yes')
        self.assertEqual(out['item']['payload'], {'go': 1})
        self.assertIsNone(self.p.get(card['id']))

    def test_respond_no_clears_all(self):
        self.p.add('k', 'ا', 'a', '', {})
        self.p.add('k', 'ب', 'b', '', {})
        out = self.p.respond('الغِ')
        self.assertEqual(out['verdict'], 'no')
        self.assertEqual(self.p.list(), [])

    def test_respond_ambiguous_when_many(self):
        self.p.add('k', 'ا', 'a', '', {})
        self.now[0] += 1
        self.p.add('k', 'ب', 'b', '', {})
        out = self.p.respond('نعم')
        self.assertEqual(out['verdict'], 'ambiguous')
        self.assertEqual(len(self.p.list()), 2)             # nothing ran

    def test_respond_non_answer(self):
        self.p.add('k', 'ا', 'a', '', {})
        self.assertEqual(self.p.respond('كم الساعة؟')['verdict'], None)

    def test_max_items_evicts_oldest(self):
        p = pending.PendingActions(clock=lambda: self.now[0], max_items=3)
        ids = []
        for i in range(5):
            self.now[0] += 1
            ids.append(p.add('k', 'ا', 'a', '', {'i': i})['id'])
        self.assertEqual(len(p.list()), 3)
        self.assertIsNone(p.get(ids[0]))
        self.assertIsNotNone(p.get(ids[-1]))


# ─── reminders ────────────────────────────────────────────────────────
class RemindersParsing(unittest.TestCase):
    def test_parse_minutes(self):
        now = datetime(2026, 9, 29, 12, 0).astimezone()
        due = reminders.parse_when(minutes=20, now=now)
        self.assertEqual((due - now).total_seconds(), 1200)

    def test_parse_at_today_or_tomorrow(self):
        now = datetime(2026, 9, 29, 12, 0).astimezone()
        later = reminders.parse_when(at='19:30', now=now)
        self.assertEqual((later.hour, later.minute, later.day), (19, 30, 29))
        passed = reminders.parse_when(at='08:00', now=now)          # already gone today
        self.assertEqual(passed.day, 30)

    def test_parse_date(self):
        due = reminders.parse_when(date='2026-12-31', at='23:00')
        self.assertEqual((due.year, due.month, due.day, due.hour), (2026, 12, 31, 23))

    def test_bad_time(self):
        with self.assertRaises(ValueError):
            reminders.parse_when(at='25:00')
        with self.assertRaises(ValueError):
            reminders.parse_when(minutes=-3)


class RemindersStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='mira-rem-')
        self.path = Path(self.dir) / 'r.json'
        self.r = reminders.Reminders(self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_add_persists_0600(self):
        self.r.add('أطفئ الفرن', 30, kind='timer')
        self.assertTrue(self.path.exists())
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(len(reminders.Reminders(self.path).list()), 1)

    def test_due_fires_once_for_oneshot(self):
        now = datetime.now().astimezone()
        self.r.add('نبّهني', now - timedelta(seconds=5))
        fired = self.r.due(now)
        self.assertEqual(len(fired), 1)
        self.assertEqual(self.r.due(now), [])               # not again

    def test_due_reschedules_daily(self):
        now = datetime.now().astimezone().replace(microsecond=0)
        self.r.add('يومي', now - timedelta(seconds=1), repeat='daily')
        fired = self.r.due(now)
        self.assertEqual(len(fired), 1)
        nxt = self.r.next_due(now)
        self.assertIsNotNone(nxt)
        self.assertGreater(datetime.fromisoformat(nxt['due']), now)

    def test_weekdays_skips_weekend(self):
        # A Friday 20:00 start; next weekday occurrence is Monday.
        friday = datetime(2026, 9, 25, 20, 0).astimezone()
        self.r.add('عمل', friday, repeat='weekdays')
        self.r.due(friday + timedelta(seconds=1))
        nxt = datetime.fromisoformat(self.r.next_due(friday + timedelta(seconds=1))['due'])
        self.assertEqual(nxt.weekday(), 0)                  # Monday

    def test_cancel_by_text(self):
        self.r.add('اجتماع مهم', 60)
        out = self.r.cancel('اجتماع')
        self.assertEqual(out['status'], 'ok')
        self.assertEqual(self.r.list(), [])

    def test_spoken_when_arabic(self):
        dt = datetime(2026, 9, 29, 19, 30).astimezone()
        self.assertIn('الساعة 7', reminders.spoken_when(dt))
        self.assertIn('مساء', reminders.spoken_when(dt))


# ─── routines ─────────────────────────────────────────────────────────
class RoutinesStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='mira-rou-')
        self.path = Path(self.dir) / 'r.json'
        self.r = routines.Routines(self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def _steps(self):
        return [{'tool': 'current_time', 'args': {}},
                {'tool': 'current_weather', 'args': {'city': 'دبي'}, 'say': 'الطقس'}]

    def test_save_and_persist_0600(self):
        self.r.save('صباح الخير', self._steps(), description='روتين الصباح')
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(self.r.get('صباح الخير')['steps'][1]['tool'], 'current_weather')
        self.assertEqual(len(self.r.list()), 1)

    def test_save_rejects_command_tool_names(self):
        with self.assertRaises(ValueError):
            self.r.save('bad', [{'tool': 'ls -la', 'args': {}}])
        with self.assertRaises(ValueError):
            self.r.save('nested', [{'tool': 'run_routine', 'args': {'name': 'x'}}])

    def test_step_limit(self):
        with self.assertRaises(ValueError):
            self.r.save('big', [{'tool': 'current_time', 'args': {}}] * 13)

    def test_run_all_ok(self):
        self.r.save('r', self._steps())
        calls = []

        def runner(tool, args):
            calls.append(tool)
            return {'status': 'ok', 'summary': tool}
        out = self.r.run('r', runner)
        self.assertEqual(out['status'], 'ok')
        self.assertEqual(out['ran'], 2)
        self.assertEqual(calls, ['current_time', 'current_weather'])

    def test_run_stops_on_error(self):
        self.r.save('r', [{'tool': 'current_time', 'args': {}},
                          {'tool': 'current_weather', 'args': {}},
                          {'tool': 'current_time', 'args': {}}])

        def runner(tool, args):
            return {'status': 'error' if tool == 'current_weather' else 'ok', 'summary': tool}
        out = self.r.run('r', runner)
        self.assertEqual(out['status'], 'partial')
        self.assertTrue(out['stopped_early'])
        self.assertEqual(out['ran'], 2)                     # third step never ran

    def test_continue_on_error(self):
        self.r.save('r', [{'tool': 'current_weather', 'args': {}, 'continue_on_error': True},
                          {'tool': 'current_time', 'args': {}}])

        def runner(tool, args):
            return {'status': 'error' if tool == 'current_weather' else 'ok', 'summary': tool}
        out = self.r.run('r', runner)
        self.assertEqual(out['ran'], 2)
        self.assertFalse(out['stopped_early'])

    def test_runner_exception_is_a_failed_step(self):
        self.r.save('r', [{'tool': 'current_time', 'args': {}}])

        def runner(tool, args):
            raise RuntimeError('boom')
        out = self.r.run('r', runner)
        self.assertEqual(out['status'], 'partial')
        self.assertEqual(out['steps'][0]['status'], 'error')

    def test_arun_async_runner(self):
        self.r.save('r', self._steps())

        async def runner(tool, args):
            await asyncio.sleep(0)
            return {'status': 'ok', 'summary': tool}
        out = asyncio.run(self.r.arun('r', runner))
        self.assertEqual(out['status'], 'ok')
        self.assertEqual(out['ran'], 2)

    def test_run_missing_raises(self):
        with self.assertRaises(KeyError):
            self.r.run('nope', lambda t, a: {'status': 'ok'})

    def test_depth_limit(self):
        self.r.save('r', self._steps())
        with self.assertRaises(ValueError):
            self.r.run('r', lambda t, a: {'status': 'ok'}, depth=2)

    def test_delete(self):
        self.r.save('r', self._steps())
        self.assertEqual(self.r.delete('r')['status'], 'ok')
        self.assertEqual(self.r.list(), [])


# ─── announce (offline) ───────────────────────────────────────────────
class AnnounceOffline(unittest.TestCase):
    def test_unsupported_without_key(self):
        with mock.patch.object(announce, '_read_key', return_value=None):
            out = announce.synthesize('مرحبا')
        self.assertEqual(out['status'], 'unsupported')
        self.assertIn('summary', out)

    def test_empty_text(self):
        self.assertEqual(announce.synthesize('   ')['status'], 'error')

    def test_write_and_16k_and_cleanup(self):
        # A fabricated 24 kHz tone through the real writer + resampler, no network.
        import array
        import math
        d = tempfile.mkdtemp(prefix='mira-ann-')
        with mock.patch.object(announce, 'CACHE_DIR', Path(d)):
            samples = array.array('h', [int(8000 * math.sin(2 * math.pi * 300 * i / 24000))
                                        for i in range(2400)])          # 0.1 s
            pcm = samples.tobytes()

            def fake_call(key, model, text, voice, timeout):
                return 200, '', pcm, 24000
            with mock.patch.object(announce, '_read_key', return_value='k'), \
                 mock.patch.object(announce, '_call', side_effect=fake_call):
                out = announce.synthesize('اختبار', also_16k=True)
            self.assertEqual(out['status'], 'ok')
            self.assertTrue(Path(out['path']).exists())
            self.assertEqual(stat.S_IMODE(Path(out['path']).stat().st_mode), 0o600)
            import wave
            with wave.open(out['path_16k']) as w:
                self.assertEqual(w.getframerate(), 16000)
                self.assertEqual(w.getnchannels(), 1)
            # cleanup removes files older than the age threshold
            old = Path(d) / 'stale.wav'
            old.write_bytes(b'RIFF')
            os.utime(old, (time.time() - 7200, time.time() - 7200))
            self.assertGreaterEqual(announce.cleanup(), 1)
            self.assertFalse(old.exists())

    def test_to_16k_ratio(self):
        import array
        pcm = array.array('h', [100] * 2400).tobytes()      # 0.1 s @ 24k
        out = announce.to_16k_mono(pcm, 24000)
        self.assertAlmostEqual(len(out) // 2, 1600, delta=40)


# ─── desktop_tools: mocked subprocess + live read-only ────────────────
class DesktopMocked(unittest.TestCase):
    def test_open_url_rejects_non_http(self):
        for bad in ['ftp://x', 'file:///etc/passwd', 'javascript:1', '', 'moos://x']:
            self.assertEqual(desktop_tools.open_url(bad)['status'], 'error', bad)

    def test_open_path_rejects_outside_home(self):
        out = desktop_tools.open_path('/etc/passwd')
        self.assertEqual(out['status'], 'error')
        self.assertIn(out['error'], ('outside_home', 'not_found'))

    def test_open_path_never_runs_code(self):
        folder = Path(tempfile.mkdtemp(prefix='mira-open-', dir=str(Path.home() / '.cache')))
        try:
            cases = {'launcher.desktop': b'[Desktop Entry]\nExec=true\n', 'tool.sh': b'echo hi\n',
                     'noext': b'#!/bin/sh\necho hi\n', 'prog': b'\x7fELF....'}
            with patch.object(desktop_tools, '_detached_open', return_value=(True, 'test')) as opener:
                for name, data in cases.items():
                    target = folder / name
                    target.write_bytes(data)
                    out = desktop_tools.open_path(str(target))
                    self.assertEqual(out.get('error'), 'executable', name)
                document = folder / 'notes.txt'
                document.write_text('hello')
                self.assertEqual(desktop_tools.open_path(str(document))['status'], 'ok')
                self.assertEqual(desktop_tools.open_path(str(folder))['status'], 'ok')
            self.assertEqual(opener.call_count, 2)
        finally:
            import shutil
            shutil.rmtree(folder, ignore_errors=True)

    def test_open_path_missing(self):
        out = desktop_tools.open_path(str(Path.home() / 'no-such-file-xyz-123'))
        self.assertEqual(out['error'], 'not_found')

    def test_media_bad_action(self):
        self.assertEqual(desktop_tools.media('destroy')['status'], 'unsupported')

    def test_find_files_scandir_fallback(self):
        # Force the scandir path by pretending Baloo is absent, over a temp HOME.
        d = tempfile.mkdtemp(prefix='mira-find-')
        home = Path(d)
        (home / 'Documents').mkdir()
        (home / 'Documents' / 'ملف-تقرير.txt').write_text('x')
        (home / 'Downloads').mkdir()
        (home / 'Downloads' / 'notes.md').write_text('y')
        with mock.patch.object(desktop_tools, 'HOME', home), \
             mock.patch.object(desktop_tools, '_baloo_search', return_value=None):
            out = desktop_tools.find_files('تقرير', 5)
            self.assertEqual(out['status'], 'ok')
            self.assertEqual(out['source'], 'scandir')
            self.assertEqual(out['count'], 1)
            self.assertTrue(out['files'][0]['name'].endswith('.txt'))
            miss = desktop_tools.find_files('لا-يوجد-هذا', 5)
            self.assertEqual(miss['count'], 0)

    def test_media_parses_busctl_and_picks_playing(self):
        names = ['org.mpris.MediaPlayer2.vlc', 'org.mpris.MediaPlayer2.firefox',
                 'org.mpris.MediaPlayer2.playerctld', 'org.kde.KWin']

        def fake_busctl(argv, timeout=6.0):
            if argv[:1] == ['call'] and 'ListNames' in argv:
                return {'data': [names]}
            if argv[:1] == ['get-property']:
                service = argv[1]
                prop = argv[-1]
                if prop == 'PlaybackStatus':
                    return 'Playing' if 'firefox' in service else 'Paused'
                if prop == 'Metadata':
                    return {'xesam:title': 'Song', 'xesam:artist': ['A']}
            return {}
        with mock.patch.object(desktop_tools, '_session_bus_ok', return_value=True), \
             mock.patch.object(desktop_tools, '_busctl', side_effect=fake_busctl):
            out = desktop_tools.media('status')
            self.assertEqual(out['status'], 'ok')
            self.assertEqual(out['player'], 'firefox')       # the playing one
            self.assertEqual(out['title'], 'Song')

    def test_system_volume_app_bad_value(self):
        self.assertEqual(desktop_tools.system_volume_app('x', 500)['status'], 'error')

    def test_media_unwraps_real_busctl_metadata_variants(self):
        def busctl(argv, timeout=6.0):
            if argv[-1] == 'PlaybackStatus':
                return {'type': 's', 'data': 'Playing'}
            return {'type': 'a{sv}', 'data': {
                'xesam:title': {'type': 's', 'data': 'حالة خاصة'},
                'xesam:artist': {'type': 'as', 'data': ['Artist', 'Second artist']},
                'mpris:length': {'type': 'x', 'data': 1835306000},
            }}
        with mock.patch.object(desktop_tools, '_busctl', side_effect=busctl):
            out = desktop_tools._player_status('org.mpris.MediaPlayer2.moplayer')
        self.assertEqual(out['state'], 'Playing')
        self.assertEqual(out['title'], 'حالة خاصة')
        self.assertEqual(out['artist'], 'Artist, Second artist')


class WindowById(unittest.TestCase):
    """focus_window_id / close_window_id act on the one window the owner clicked, by KWin's id, and
    only while its caption is the one he saw. KWin is stood in for: nothing touches the session."""

    WINDOWS = [
        {'id': '{aaaa-1}', 'caption': '~ : bash — Konsole', 'cls': 'konsole', 'normal': True},
        {'id': '{bbbb-2}', 'caption': '~ : bash — Konsole', 'cls': 'konsole', 'normal': True},
        {'id': '{cccc-3}', 'caption': 'x' * 150, 'cls': 'kate', 'normal': True},
    ]

    def run_with(self, call, *args):
        scripts = []

        def kwin(template, subst, timeout=6.0):
            scripts.append(dict(subst))
            return [dict(w) for w in self.WINDOWS] if template is desktop_tools._WINDOWS_JS else {'done': 1}
        with mock.patch.object(desktop_tools, '_session_bus_ok', return_value=True), \
                mock.patch.object(desktop_tools, '_kwin_available', return_value=True), \
                mock.patch.object(desktop_tools, '_run_kwin_script', side_effect=kwin):
            return call(*args), scripts

    def test_the_exact_window_among_two_with_one_title(self):
        # By title the two Konsoles are ambiguous; by id the second one is closed, and only it.
        out, scripts = self.run_with(desktop_tools.close_window, '~ : bash — Konsole')
        self.assertEqual(out.get('error'), 'ambiguous')
        out, scripts = self.run_with(desktop_tools.close_window_id, '{bbbb-2}', '~ : bash — Konsole')
        self.assertEqual(out['status'], 'ok', out)
        self.assertEqual(scripts[-1], {'wid': '{bbbb-2}', 'mode': 'close'})
        out, scripts = self.run_with(desktop_tools.focus_window_id, '{aaaa-1}', '~ : bash  —  Konsole')
        self.assertEqual(out['status'], 'ok', out)
        self.assertEqual(scripts[-1], {'wid': '{aaaa-1}', 'mode': 'focus'})

    def test_a_changed_caption_or_a_gone_window_does_nothing(self):
        out, scripts = self.run_with(desktop_tools.close_window_id, '{bbbb-2}', 'Report — Writer')
        self.assertEqual((out['status'], out['error']), ('partial', 'caption_changed'))
        self.assertEqual(len(scripts), 1, 'only the list was read; no action ran')
        out, scripts = self.run_with(desktop_tools.close_window_id, '{dddd-4}', 'Anything')
        self.assertEqual(out['error'], 'no_match')
        self.assertEqual(len(scripts), 1)

    def test_a_title_cut_for_the_card_still_names_its_window(self):
        out, _ = self.run_with(desktop_tools.close_window_id, '{cccc-3}', 'x' * 120)
        self.assertEqual(out['status'], 'ok', out)
        out, _ = self.run_with(desktop_tools.close_window_id, '{cccc-3}', 'x' * 60)
        self.assertEqual(out['error'], 'caption_changed', 'a short title must match whole')

    def test_bad_ids_are_refused_before_kwin(self):
        for wid in ('', 'a b', '"); workspace.x(); ("', 'x' * 65):
            out, scripts = self.run_with(desktop_tools.close_window_id, wid, 't')
            self.assertEqual(out['error'], 'bad_window', wid)
            self.assertEqual(scripts, [])


@unittest.skipUnless(_live_tests_asked(), "reads the owner's live desktop; set MIRA_LIVE_TESTS=1 to run")
@unittest.skipUnless(_has_session(), 'no desktop session bus')
class DesktopLive(unittest.TestCase):
    """One real, read-only observation each, on request only (MIRA_LIVE_TESTS=1). These print what
    they saw, and the clipboard check prints only its summary, never what was copied."""

    def test_media_status_live(self):
        out = desktop_tools.media('status')
        self.assertIn(out['status'], ('ok', 'unsupported', 'partial'))
        print('\n[live] media status ->', out.get('summary'))

    def test_clipboard_read_live(self):
        out = desktop_tools.clipboard_read()
        self.assertIn(out['status'], ('ok', 'unsupported'))
        print('[live] clipboard read ->', out.get('summary'))

    def test_list_windows_live(self):
        out = desktop_tools.list_windows()
        self.assertIn(out['status'], ('ok', 'unsupported'))
        print('[live] list_windows ->', out.get('summary'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
