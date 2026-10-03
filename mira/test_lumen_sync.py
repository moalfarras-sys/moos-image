"""Lumen screen sync: colour analysis on synthetic frames, the capture pipeline on videotestsrc, and
the ScreenCast portal sequence against a fake session bus. Nothing here opens a real portal session:
that would put an approval dialog on the owner's screen."""
import os
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from lumen import sync
from lumen import capture

W, H = 64, 36


def solid(rgb, w=W, h=H):
    return bytes(rgb) * (w * h)


def paint(frame, rgb, x0, y0, x1, y1, w=W):
    """Fill pixel rect [x0, x1) x [y0, y1) of a bytearray frame."""
    px = bytes(rgb)
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * w + x) * 3
            frame[i:i + 3] = px
    return frame


def saturation(rgb):
    hi, lo = max(rgb), min(rgb)
    return 0.0 if hi == 0 else (hi - lo) / hi


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class AnalyzerColourTest(unittest.TestCase):
    def test_solid_primaries_and_white_come_back_unchanged(self):
        for rgb in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)):
            for mode in sync.MODES:
                self.assertEqual(sync.Analyzer(mode).ambient(solid(rgb), W, H), rgb, (rgb, mode))

    def test_solid_colour_keeps_its_hue_and_never_brightens(self):
        out = sync.Analyzer('video').ambient(solid((230, 120, 30)), W, H)
        self.assertEqual(out.index(max(out)), 0)
        self.assertGreater(out[1], out[2])
        self.assertLessEqual(max(out), 230)
        self.assertGreaterEqual(saturation(out), saturation((230, 120, 30)))

    def test_gamma_keeps_a_grey_scene_dimmer_than_the_screen(self):
        out = sync.Analyzer('video').ambient(solid((128, 128, 128)), W, H)
        self.assertEqual(len(set(out)), 1)               # grey stays grey: no invented tint
        self.assertLess(out[0], 128)
        self.assertGreater(out[0], 0)

    def test_dark_scene_with_a_red_sun_is_red_not_grey(self):
        frame = paint(bytearray(solid((12, 12, 14))), (255, 60, 20), 8, 4, 14, 10)  # 36 px of 2304
        out = sync.Analyzer('video').ambient(bytes(frame), W, H)
        self.assertGreater(out[0], 3 * max(out[1], out[2]), out)
        self.assertGreater(out[0], 40, out)              # visible, not floored away
        self.assertLess(out[0], 200, out)                # yet dimmer than a screen full of sun

    def test_grey_scene_with_a_red_sun_is_red(self):
        frame = paint(bytearray(solid((90, 90, 90))), (255, 40, 20), 8, 4, 14, 10)
        out = sync.Analyzer('video').ambient(bytes(frame), W, H)
        plain = [sum(frame[i::3]) / (W * H) for i in range(3)]
        self.assertLess(saturation(plain), 0.2)          # the plain mean would be grey
        self.assertGreater(saturation(out), 0.8, out)
        self.assertEqual(out.index(max(out)), 0)

    def test_black_and_near_black_go_dark(self):
        for rgb in ((0, 0, 0), (6, 6, 6), (10, 4, 4)):
            for mode in sync.MODES:
                self.assertEqual(sync.Analyzer(mode).ambient(solid(rgb), W, H), (0, 0, 0), (rgb, mode))

    def test_floor_has_hysteresis(self):
        clock = Clock()
        a = sync.Analyzer('game', clock=clock)
        floor = sync.MODES['game'].min_brightness
        # find a grey whose output level sits between the floor and the return threshold
        between = None
        for v in range(1, 120):
            level = max(sync.Analyzer('game').ambient(solid((v, v, v)), W, H)) / 255
            if floor < level < floor * sync.FLOOR_RETURN:
                between = v
                break
        self.assertIsNotNone(between)
        self.assertNotEqual(a.ambient(solid((between,) * 3), W, H), (0, 0, 0))   # on stays on
        clock.t += 5
        self.assertEqual(a.ambient(solid((0, 0, 0)), W, H), (0, 0, 0))
        clock.t += 5
        self.assertEqual(a.ambient(solid((between,) * 3), W, H), (0, 0, 0))      # off stays off

    def test_brightness_scales_the_level(self):
        full = sync.Analyzer('video').ambient(solid((200, 60, 30)), W, H)
        half = sync.Analyzer('video', brightness=0.5).ambient(solid((200, 60, 30)), W, H)
        self.assertAlmostEqual(max(half) / max(full), 0.5, delta=0.02)

    def test_saturation_setting_overrides_the_mode(self):
        rgb = (200, 140, 120)
        plain = sync.Analyzer('video', saturation=1.0).ambient(solid(rgb), W, H)
        boosted = sync.Analyzer('video', saturation=2.0).ambient(solid(rgb), W, H)
        self.assertGreater(saturation(boosted), saturation(plain))
        self.assertEqual(max(plain), max(boosted))       # the boost keeps the peak channel

    def test_bad_input_is_refused(self):
        a = sync.Analyzer()
        with self.assertRaises(ValueError):
            a.ambient(b'\0' * 10, W, H)
        with self.assertRaises(ValueError):
            a.regions(solid((1, 2, 3)), W, H, {'x': (0.5, 0, 0.2, 1)})
        with self.assertRaises(ValueError):
            a.gradient(solid((1, 2, 3)), W, H, 4, 'diagonal')
        with self.assertRaises(ValueError):
            sync.Analyzer('disco')
        with self.assertRaises(ValueError):
            sync.Analyzer(brightness=1.5)


class LetterboxTest(unittest.TestCase):
    RECTS = {'top': (0, 0, 1, 0.3), 'bottom': (0, 0.7, 1, 1), 'left': (0, 0, 0.3, 1),
             'right': (0.7, 0, 1, 1), 'all': (0, 0, 1, 1)}

    def letterboxed(self, rgb, top=4, bottom=5):
        """2.39:1 on 16:9: 27 picture rows of 36, the odd remainder in the bottom bar."""
        return paint(bytearray(solid((0, 0, 0))), rgb, 0, top, W, H - bottom)

    def test_bars_do_not_darken_any_region(self):
        rgb = (200, 80, 40)
        expected = sync.Analyzer('video').regions(solid(rgb), W, H, self.RECTS)
        a = sync.Analyzer('video')
        got = a.regions(bytes(self.letterboxed(rgb)), W, H, self.RECTS)
        self.assertEqual(got, expected)
        self.assertEqual(a.picture, (0.0, 4 / 36, 1.0, 31 / 36))

    def test_regions_map_into_the_picture(self):
        frame = self.letterboxed((0, 0, 255))
        paint(frame, (255, 0, 0), 0, 18, W, 31)          # lower half of the picture is red
        got = sync.Analyzer('video').regions(bytes(frame), W, H, {'top': (0, 0, 1, 0.3),
                                                                 'bottom': (0, 0.7, 1, 1)})
        self.assertEqual(got['top'], sync.Analyzer('video').ambient(solid((0, 0, 255)), W, H))
        self.assertEqual(got['bottom'], sync.Analyzer('video').ambient(solid((255, 0, 0)), W, H))

    def test_subtitles_in_the_bottom_bar_do_not_cancel_it(self):
        frame = self.letterboxed((200, 80, 40))
        for x in range(20, 44, 2):                       # a line of white text in the bottom bar
            paint(frame, (255, 255, 255), x, 33, x + 1, 34)
        a = sync.Analyzer('video')
        a.regions(bytes(frame), W, H, self.RECTS)
        self.assertEqual(a.picture, (0.0, 4 / 36, 1.0, 31 / 36))

    def test_pillarbox(self):
        rgb = (40, 160, 90)
        frame = paint(bytearray(solid((0, 0, 0))), rgb, 8, 0, 56, H)   # 4:3 inside 16:9
        expected = sync.Analyzer('video').regions(solid(rgb), W, H, self.RECTS)
        a = sync.Analyzer('video')
        self.assertEqual(a.regions(bytes(frame), W, H, self.RECTS), expected)
        self.assertEqual(a.picture, (8 / 64, 0.0, 56 / 64, 1.0))

    def test_a_dark_edge_on_one_side_is_scene_not_bar(self):
        frame = paint(bytearray(solid((200, 80, 40))), (0, 0, 0), 0, 0, W, 6)   # night sky on top
        a = sync.Analyzer('video')
        a.ambient(bytes(frame), W, H)
        self.assertEqual(a.picture, (0.0, 0.0, 1.0, 1.0))

    def test_black_frame_keeps_the_bars_and_bars_appear_only_after_holding(self):
        clock = Clock()
        a = sync.Analyzer('video', clock=clock)
        a.ambient(solid((200, 80, 40)), W, H)                     # full picture first
        self.assertEqual(a.picture, (0.0, 0.0, 1.0, 1.0))
        boxed = bytes(self.letterboxed((200, 80, 40)))
        for _ in range(30):                                       # dark edges for one second
            clock.t += 1 / 30
            a.ambient(boxed, W, H)
            self.assertEqual(a.picture, (0.0, 0.0, 1.0, 1.0))    # could be a dark scene
        clock.t += sync.BAR_HOLD
        a.ambient(boxed, W, H)
        self.assertEqual(a.picture, (0.0, 4 / 36, 1.0, 31 / 36))  # held: believed
        clock.t += 0.1
        a.ambient(solid((0, 0, 0)), W, H)                         # black between scenes
        self.assertEqual(a.picture, (0.0, 4 / 36, 1.0, 31 / 36))
        clock.t += 0.1
        a.ambient(solid((10, 200, 10)), W, H)                     # picture in the bar: gone now
        self.assertEqual(a.picture, (0.0, 0.0, 1.0, 1.0))


class ChannelMappingTest(unittest.TestCase):
    def test_left_red_right_blue_reaches_the_left_and_right_lights(self):
        frame = paint(bytearray(solid((255, 0, 0))), (0, 0, 255), 32, 0, W, H)
        rects = sync.regions_for_channels([{'id': 3, 'x': -0.9, 'y': 0.5, 'z': 0.0},
                                           {'id': 7, 'x': 0.9, 'y': 0.5, 'z': 0.0}])
        got = sync.Analyzer('video').regions(bytes(frame), W, H, rects)
        self.assertEqual(got, {'3': (255, 0, 0), '7': (0, 0, 255)})

    def test_height_picks_a_third_and_the_middle_reads_the_centre(self):
        rects = sync.regions_for_channels([
            {'id': 1, 'x': -0.8, 'y': 0, 'z': 0.9}, {'id': 2, 'x': 0.8, 'y': 0, 'z': -0.9},
            {'id': 3, 'x': 0.05, 'y': 0, 'z': 0.1}, {'id': 4, 'x': 0.9, 'y': 0, 'z': 0.0},
            {'channel_id': 5, 'position': {'x': -1.0, 'y': 0, 'z': -1.0}},
        ])
        x0, y0, x1, y1 = rects['1']
        self.assertEqual((x0, y0), (0.0, 0.0))
        self.assertLessEqual(y1, 0.34)
        self.assertGreaterEqual(rects['2'][1], 0.66)
        self.assertEqual(rects['2'][2], 1.0)
        cx0, cy0, cx1, cy1 = rects['3']
        self.assertTrue(cx0 < 0.5 < cx1 and cy0 < 0.5 < cy1 and cx0 > 0 and cx1 < 1)
        self.assertEqual((rects['4'][1], rects['4'][3]), (0.0, 1.0))
        self.assertEqual(rects['5'][0], 0.0)
        for rect in rects.values():
            self.assertTrue(0 <= rect[0] < rect[2] <= 1 and 0 <= rect[1] < rect[3] <= 1, rect)

    def test_names_spread_left_to_right(self):
        rects = sync.regions_for_names(['light.a', 'light.b', 'light.c'])
        self.assertEqual(list(rects), ['light.a', 'light.b', 'light.c'])
        self.assertEqual(rects['light.a'][0], 0.0)
        self.assertEqual(rects['light.c'][2], 1.0)
        self.assertEqual(rects['light.a'][2], rects['light.b'][0])
        frame = paint(bytearray(solid((255, 0, 0))), (0, 255, 0), 22, 0, 43, H)
        paint(frame, (0, 0, 255), 43, 0, W, H)
        got = sync.Analyzer('game').regions(bytes(frame), W, H, rects)
        self.assertEqual([v.index(max(v)) for v in got.values()], [0, 1, 2])


class GradientTest(unittest.TestCase):
    def test_bottom_edge_runs_left_to_right(self):
        frame = paint(bytearray(solid((255, 0, 0))), (0, 0, 255), 32, 0, W, H)
        out = sync.Analyzer('game').gradient(bytes(frame), W, H, 8, 'bottom')
        self.assertEqual(len(out), 8)
        self.assertEqual(out[0], (255, 0, 0))
        self.assertEqual(out[-1], (0, 0, 255))

    def test_left_edge_runs_top_to_bottom_and_around_is_clockwise(self):
        frame = paint(bytearray(solid((255, 0, 0))), (0, 0, 255), 0, 18, W, H)  # bottom half blue
        a = sync.Analyzer('game')
        left = a.gradient(bytes(frame), W, H, 4, 'left')
        self.assertEqual((left[0], left[-1]), ((255, 0, 0), (0, 0, 255)))
        around = a.gradient(bytes(frame), W, H, 20, 'around')
        self.assertEqual(len(around), 20)
        self.assertEqual(around[0], (0, 0, 255))         # starts bottom-left, going up
        self.assertIn((255, 0, 0), around[5:12])         # the top run
        self.assertEqual(around[-1], (0, 0, 255))        # ends along the bottom


class SmoothingTest(unittest.TestCase):
    def run_step(self, mode, before, after, seconds, fps=30):
        clock = Clock()
        a = sync.Analyzer(mode, clock=clock)
        first = a.ambient(solid(before), W, H)
        target = sync.Analyzer(mode).ambient(solid(after), W, H)
        seq = []
        frame = solid(after)
        for _ in range(int(seconds * fps)):
            clock.t += 1 / fps
            seq.append(a.ambient(frame, W, H))
        return first, target, seq

    def test_converges_without_overshoot(self):
        for mode in sync.MODES:
            settle = 10 * max(sync.MODES[mode].smoothing) + 1
            for before, after in (((60, 20, 10), (240, 80, 40)), ((240, 80, 40), (60, 20, 10)),
                                  ((200, 0, 0), (0, 0, 200))):
                first, target, seq = self.run_step(mode, before, after, settle)
                for c in range(3):
                    lo, hi = sorted((first[c], target[c]))
                    for v in seq:
                        self.assertTrue(lo <= v[c] <= hi, (mode, before, after, c, v))
                    path = [first[c]] + [v[c] for v in seq]
                    steps = [b - a for a, b in zip(path, path[1:])]
                    self.assertTrue(all(s >= 0 for s in steps) or all(s <= 0 for s in steps),
                                    (mode, c, path))
                self.assertEqual(seq[-1], target, mode)

    def test_game_reacts_faster_than_video_faster_than_ambient(self):
        progress = {}
        for mode in sync.MODES:
            first, target, seq = self.run_step(mode, (40, 40, 160), (220, 60, 20), 0.2)
            progress[mode] = (seq[-1][0] - first[0]) / (target[0] - first[0])
        self.assertGreater(progress['game'], 0.95)
        self.assertGreater(progress['game'], progress['video'])
        self.assertGreater(progress['video'], progress['ambient'])
        self.assertLess(progress['ambient'], 0.5)

    def test_smoothing_follows_time_not_frame_count(self):
        clock = Clock()
        slow, fast = sync.Analyzer('video', clock=clock), sync.Analyzer('video', clock=clock)
        slow.ambient(solid((30, 30, 120)), W, H)
        fast.ambient(solid((30, 30, 120)), W, H)
        frame = solid((220, 60, 20))
        for i in range(1, 31):                           # one second: 30 frames vs 2 frames
            clock.t += 1 / 30
            f = fast.ambient(frame, W, H)
            if i % 15 == 0:
                s = slow.ambient(frame, W, H)
        self.assertLessEqual(abs(f[0] - s[0]), 2, (f, s))


class AnalysisCostTest(unittest.TestCase):
    def test_one_frame_for_seven_lights_is_cheap(self):
        frames = [bytes((i * 7 + j * 13) % 256 for j in range(W * H * 3)) for i in range(8)]
        rects = sync.regions_for_channels([{'id': i, 'x': -0.9 + 0.3 * i, 'z': 0.5} for i in range(7)])
        a = sync.Analyzer('game')
        t0 = time.perf_counter()
        for _ in range(10):
            for f in frames:
                a.regions(f, W, H, rects)
        per_frame = (time.perf_counter() - t0) / 80
        self.assertLess(per_frame, 0.02)                 # generous: measured 1-2 ms on the station


# ── capture ──────────────────────────────────────────────────────────
def gst_or_skip():
    if capture.Gst is None:
        raise unittest.SkipTest('GStreamer for Python is not available')
    capture.Gst.init(None)
    for element in ('videotestsrc', 'videoscale', 'videoconvert', 'videorate', 'appsink'):
        if capture.Gst.ElementFactory.find(element) is None:
            raise unittest.SkipTest(f'GStreamer element {element} is missing')
    return capture.Gst


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class TestSourceCaptureTest(unittest.TestCase):
    def setUp(self):
        self.Gst = gst_or_skip()

    def test_frames_have_the_right_size_and_rate_and_stop_releases(self):
        frames = []
        cap = capture.ScreenCapture(lambda d, w, h: frames.append((len(d), w, h)), fps=15, source='test')
        cap.start()
        self.assertTrue(wait_for(lambda: cap.state == 'running'), cap.stats())
        pipeline = cap._pipeline
        time.sleep(2.2)
        stats = cap.stats()
        self.assertEqual(stats['state'], 'running')
        self.assertTrue(11 <= stats['fps'] <= 19, stats)
        self.assertTrue(frames and all(f == (W * H * 3, W, H) for f in frames))
        cap.stop()
        self.assertEqual(cap.state, 'idle')
        self.assertFalse(cap._thread.is_alive())
        self.assertIsNone(cap._pipeline)
        self.assertEqual(pipeline.get_state(0)[1], self.Gst.State.NULL)
        seen = len(frames)
        time.sleep(0.3)
        self.assertEqual(len(frames), seen)
        cap.stop()                                        # idempotent
        cap.start()                                       # and it starts again
        self.assertTrue(wait_for(lambda: len(frames) > seen + 3))
        cap.stop()

    def test_odd_width_rows_are_unpadded(self):
        frames = []
        cap = capture.ScreenCapture(lambda d, w, h: frames.append((len(d), w, h)), fps=10,
                                    width=50, height=30, source='test')
        cap.start()
        try:
            self.assertTrue(wait_for(lambda: len(frames) >= 3))
        finally:
            cap.stop()
        self.assertEqual(frames[0], (50 * 30 * 3, 50, 30))

    def test_a_dying_stream_reports_error_and_start_recovers(self):
        GLib = capture.GLib
        cap = capture.ScreenCapture(lambda *a: None, fps=15, source='test')
        cap.start()
        try:
            self.assertTrue(wait_for(lambda: cap.state == 'running'))
            p = cap._pipeline
            err = GLib.Error.new_literal(self.Gst.resource_error_quark(), 'the screen went away',
                                         int(self.Gst.ResourceError.READ))
            p.post_message(self.Gst.Message.new_error(p, err, 'test'))
            self.assertTrue(wait_for(lambda: cap.state == 'error'))
            self.assertEqual(cap.reason, 'pipeline')
            self.assertIn('the screen went away', cap.error)
            self.assertTrue(wait_for(lambda: not cap._thread.is_alive()))
            self.assertIsNone(cap._pipeline)
            cap.start()
            self.assertTrue(wait_for(lambda: cap.state == 'running'))
            self.assertEqual(cap.error, '')
        finally:
            cap.stop()

    def test_end_of_stream_and_stall_are_errors_with_reasons(self):
        class Ending(capture.ScreenCapture):
            def _test_description(self):
                return ('videotestsrc num-buffers=5 is-live=true '
                        '! video/x-raw,format=BGRx,width=320,height=180,framerate=30/1')

        class Silent(capture.ScreenCapture):
            def _test_description(self):
                return ('appsrc is-live=true format=time '
                        'caps="video/x-raw,format=BGRx,width=320,height=180,framerate=30/1"')

        ending = Ending(lambda *a: None, source='test')
        ending.start()
        self.assertTrue(wait_for(lambda: ending.state == 'error'), ending.stats())
        self.assertEqual(ending.reason, 'ended')
        ending.stop()
        with mock.patch.object(capture, 'STALL_S', 0.5):
            silent = Silent(lambda *a: None, source='test')
            silent.start()
            self.assertTrue(wait_for(lambda: silent.state == 'error', 4), silent.stats())
            self.assertEqual(silent.reason, 'stalled')
            silent.stop()

    def test_callback_errors_do_not_end_the_capture(self):
        def broken(*_):
            raise RuntimeError('consumer bug')
        cap = capture.ScreenCapture(broken, fps=15, source='test')
        cap.start()
        try:
            self.assertTrue(wait_for(lambda: cap.stats()['callback_errors'] >= 3))
            self.assertEqual(cap.state, 'running')
            self.assertIn('consumer bug', cap.stats()['callback_error'])
        finally:
            cap.stop()


# ── the portal sequence against a fake bus ───────────────────────────
REQ_PREFIX = '/org/freedesktop/portal/desktop/request/1_77/'


class FakePortalBus:
    """Just enough of Gio.DBusConnection for the ScreenCast handshake. Responses are delivered the
    way Gio delivers signals: later, on the main context that was thread-default at subscribe time."""

    def __init__(self, codes=None, tokens=('tok-1', 'tok-2', 'tok-3'), remote_fails=False):
        self.GLib = capture.GLib
        self.remote_fails = remote_fails
        self.Gio = capture.Gio
        self.codes = dict(codes or {})      # method -> response code, or None for "never answers"
        self.tokens = list(tokens)
        self.calls = []
        self.subs = {}
        self.ctx = None
        self.fd_handed = None
        self._next = 0
        self._lock = threading.Lock()

    def get_unique_name(self):
        return ':1.77'

    def signal_subscribe(self, sender, iface, member, path, arg0, flags, callback, *user_data):
        with self._lock:
            self._next += 1
            self.subs[self._next] = (iface, member, path, callback,
                                     self.GLib.MainContext.ref_thread_default())
            return self._next

    def signal_unsubscribe(self, sid):
        with self._lock:
            self.subs.pop(sid, None)

    def emit(self, iface, member, path, params):
        with self._lock:
            targets = [(cb, ctx) for i, m, p, cb, ctx in self.subs.values()
                       if (i, m, p) == (iface, member, path)]
        for cb, ctx in targets:
            src = self.GLib.idle_source_new()
            src.set_callback(lambda *_a, cb=cb: (cb(self, capture.PORTAL_BUS, path, iface, member,
                                                    params), False)[1])
            src.attach(ctx)

    def call_sync(self, name, path, iface, method, params, reply_type, flags, timeout, cancellable):
        args = params.unpack() if params is not None else ()
        self.calls.append((path, iface, method, args))
        self.ctx = self.GLib.MainContext.ref_thread_default()
        if iface != capture.CAST:
            return None
        V = self.GLib.Variant
        handle = args[-1]['handle_token']
        request = REQ_PREFIX + handle
        if method == 'CreateSession':
            results = {'session_handle': V('s', '/org/freedesktop/portal/desktop/session/1_77/'
                                           + args[0]['session_handle_token'])}
        elif method == 'Start':
            results = {'streams': V('a(ua{sv})', [(57, {'pipewire-serial': V('t', 4242),
                                                        'size': V('(ii)', (3840, 2160))})])}
            if self.tokens:
                results['restore_token'] = V('s', self.tokens.pop(0))
        else:
            results = {}
        code = self.codes.get(method, 0)
        if code is not None:
            self.emit(capture.REQUEST, 'Response', request, V('(ua{sv})', (code, results)))
        return V('(o)', (request,))

    def call_with_unix_fd_list_sync(self, name, path, iface, method, params, reply_type, flags,
                                    timeout, fd_list, cancellable):
        self.calls.append((path, iface, method, params.unpack()))
        if self.remote_fails:
            raise self.GLib.Error.new_literal(self.GLib.quark_from_string('fake-portal'),
                                              'no PipeWire remote for this session', 1)
        r, w = os.pipe()
        os.close(w)
        self.fd_handed = r
        return self.GLib.Variant('(h)', (0,)), self.Gio.UnixFDList.new_from_array([r])

    def methods(self):
        return [c[2] for c in self.calls]

    def options(self, method):
        return next(c[3][-1] for c in self.calls if c[2] == method)


class PortalCapture(capture.ScreenCapture):
    """The real handshake and pipeline, with videotestsrc standing in for pipewiresrc."""

    def _source_description(self, fd, target):
        self.seen = (fd, target)
        return self._test_description()


class PortalSequenceTest(unittest.TestCase):
    def setUp(self):
        gst_or_skip()
        self.tmp = tempfile.TemporaryDirectory()
        self.token = Path(self.tmp.name) / 'mira' / 'lumen-portal-token'

    def tearDown(self):
        self.tmp.cleanup()

    def test_sequence_options_token_and_release(self):
        bus = FakePortalBus()
        cap = PortalCapture(lambda *a: None, fps=15, token_path=self.token, bus=bus)
        with mock.patch.object(capture.os, 'close', wraps=os.close) as closed:
            cap.start()
            self.assertTrue(wait_for(lambda: cap.state == 'running'), cap.stats())
            fd, target = cap.seen
            self.assertEqual(bus.methods(), ['CreateSession', 'SelectSources', 'Start',
                                             'OpenPipeWireRemote'])
            opts = bus.options('SelectSources')
            self.assertEqual((opts['types'], opts['multiple'], opts['cursor_mode'],
                              opts['persist_mode']), (1, False, 1, 2))
            self.assertNotIn('restore_token', opts)
            self.assertEqual(target, 4242)                # the stable serial, not node id 57
            self.assertNotEqual(fd, bus.fd_handed)        # our own duplicate
            self.assertEqual(self.token.read_text(), 'tok-1')
            self.assertEqual(stat.S_IMODE(self.token.stat().st_mode), 0o600)
            cap.stop()
            self.assertIn(mock.call(fd), closed.call_args_list)
        self.assertEqual(cap.state, 'idle')
        session = bus.calls[-1]
        self.assertEqual(session[1:3], (capture.SESSION, 'Close'))
        self.assertTrue(session[0].startswith('/org/freedesktop/portal/desktop/session/'))

        # the second start (a new process, even) offers the stored token and keeps its replacement
        again = PortalCapture(lambda *a: None, fps=15, token_path=self.token, bus=bus)
        bus.calls.clear()
        again.start()
        try:
            self.assertTrue(wait_for(lambda: again.state == 'running'), again.stats())
            self.assertEqual(bus.options('SelectSources')['restore_token'], 'tok-1')
            self.assertEqual(self.token.read_text(), 'tok-2')
        finally:
            again.stop()

    def test_no_token_returned_forgets_the_consumed_one(self):
        self.token.parent.mkdir(parents=True)
        self.token.write_text('old')
        bus = FakePortalBus(tokens=())
        cap = PortalCapture(lambda *a: None, token_path=self.token, bus=bus)
        cap.start()
        try:
            self.assertTrue(wait_for(lambda: cap.state == 'running'))
            self.assertEqual(bus.options('SelectSources')['restore_token'], 'old')
            self.assertFalse(self.token.exists())
        finally:
            cap.stop()

    def test_token_is_kept_even_when_a_later_step_fails(self):
        bus = FakePortalBus(remote_fails=True)
        cap = PortalCapture(lambda *a: None, token_path=self.token, bus=bus)
        cap.start()
        self.assertTrue(wait_for(lambda: cap.state == 'error'))
        self.assertIn('no PipeWire remote', cap.error)
        self.assertEqual(cap.reason, 'portal')
        self.assertEqual(self.token.read_text(), 'tok-1')     # Start consumed the old one
        self.assertTrue(wait_for(lambda: not cap._thread.is_alive()))
        self.assertEqual(bus.methods()[-1], 'Close')

    def test_owner_declines(self):
        bus = FakePortalBus(codes={'Start': 1})
        cap = PortalCapture(lambda *a: None, token_path=self.token, bus=bus)
        cap.start()
        self.assertTrue(wait_for(lambda: cap.state == 'denied'), cap.stats())
        self.assertTrue(wait_for(lambda: not cap._thread.is_alive()))
        self.assertIn('declined', cap.error)
        self.assertEqual(bus.methods(), ['CreateSession', 'SelectSources', 'Start', 'Close'])
        self.assertFalse(self.token.exists())
        self.assertIsNone(cap._pipeline)

    def test_portal_failure_is_an_error(self):
        bus = FakePortalBus(codes={'SelectSources': 2})
        cap = PortalCapture(lambda *a: None, bus=bus)
        cap.start()
        self.assertTrue(wait_for(lambda: cap.state == 'error'))
        self.assertEqual(cap.reason, 'portal')
        self.assertTrue(wait_for(lambda: not cap._thread.is_alive()))
        self.assertEqual(bus.methods()[-1], 'Close')

    def test_stop_while_the_dialog_is_up_closes_it(self):
        bus = FakePortalBus(codes={'Start': None})       # the owner never answers
        cap = PortalCapture(lambda *a: None, bus=bus)
        cap.start()
        self.assertEqual(cap.state, 'asking')
        self.assertTrue(wait_for(lambda: 'Start' in bus.methods()))
        time.sleep(0.2)
        self.assertEqual(cap.state, 'asking')
        cap.stop()
        self.assertEqual(cap.state, 'idle')
        closes = [(c[0], c[1]) for c in bus.calls if c[2] == 'Close']
        self.assertTrue(closes[0][0].startswith(REQ_PREFIX) and closes[0][1] == capture.REQUEST,
                        closes)
        self.assertEqual(closes[1][1], capture.SESSION)

    def test_session_closed_by_the_system_is_an_error_and_restart_is_silent(self):
        bus = FakePortalBus()
        cap = PortalCapture(lambda *a: None, fps=15, bus=bus)
        cap.start()
        try:
            self.assertTrue(wait_for(lambda: cap.state == 'running'))
            session = next(c[3][0] for c in bus.calls if c[2] == 'SelectSources')
            bus.emit(capture.SESSION, 'Closed', session, capture.GLib.Variant('(a{sv})', ({},)))
            self.assertTrue(wait_for(lambda: cap.state == 'error'))
            self.assertEqual(cap.reason, 'closed')
            self.assertTrue(wait_for(lambda: not cap._thread.is_alive()))
            self.assertNotIn(('Close', session), [(c[2], c[0]) for c in bus.calls])  # already gone
            bus.calls.clear()
            cap.start()
            self.assertTrue(wait_for(lambda: cap.state == 'running'))
            self.assertEqual(bus.options('SelectSources')['restore_token'], 'tok-1')  # in memory
        finally:
            cap.stop()


if __name__ == '__main__':
    unittest.main()
